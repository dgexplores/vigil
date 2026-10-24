"""Render an isolated Oracle Compose deployment from the canonical manifests.

State and secrets belong outside the Git checkout. No cloud resources are created.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / 'bank-of-anthos'


def prepare(state, hostname, key_file=None):
    if not hostname or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-' for c in hostname):
        raise ValueError('Use a DNS hostname without spaces or URL paths')
    state = Path(state).resolve()
    if state == ROOT or ROOT in state.parents:
        raise ValueError('State must be outside the Git checkout')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    state.chmod(0o700)
    config_file = state / 'credentials.json'
    if config_file.exists():
        credentials = json.loads(config_file.read_text())
    else:
        credentials = {name: secrets.token_urlsafe(32) for name in ['ledger_password', 'accounts_password']}
        config_file.write_text(json.dumps(credentials))
        config_file.chmod(0o600)
    private = state / 'jwt.key'
    public = state / 'jwt.pub'
    if public.exists() and not private.exists():
        raise ValueError('JWT private key is missing; restore it from backup')
    if not private.exists():
        subprocess.run(['openssl', 'genrsa', '-out', str(private), '2048'], check=True, capture_output=True)
    if not public.exists():
        subprocess.run(['openssl', 'rsa', '-in', str(private), '-pubout', '-out', str(public)], check=True, capture_output=True)
    # Parent directory is private; bound files must be readable by container users.
    private.chmod(0o444)
    public.chmod(0o444)
    gemini_key = Path(key_file).read_text().strip() if key_file else ''
    if any(c.isspace() for c in gemini_key):
        raise ValueError('Gemini key must be a single token')
    env_file = state / 'agents.env'
    env_file.write_text('GEMINI_API_KEY=' + gemini_key + '\nGEMINI_MODEL=gemini-3.8-flash\n')
    env_file.chmod(0o600)
    manifests = {}
    for path in (BANK / 'kubernetes-manifests').glob('*.yaml'):
        if path.name.startswith('._'):
            continue
        for item in yaml.safe_load_all(path.read_text()):
            if item:
                manifests[(item['kind'], item['metadata']['name'])] = item
    maps = {name: item['data'].copy() for (kind, name), item in manifests.items() if kind == 'ConfigMap'}
    maps['ledger-db-config'].update(POSTGRES_PASSWORD=credentials['ledger_password'], SPRING_DATASOURCE_PASSWORD=credentials['ledger_password'])
    maps['accounts-db-config'].update(POSTGRES_PASSWORD=credentials['accounts_password'], ACCOUNTS_DB_URI=f"postgresql://accounts-admin:{credentials['accounts_password']}@accounts-db:5432/accounts-db")
    services = {}
    python_health = {'test': ['CMD', 'python', '-c', "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/ready',timeout=5)"], 'interval': '15s', 'timeout': '10s', 'retries': 12, 'start_period': '90s'}
    paths = {'frontend': 'frontend', 'userservice': 'accounts/userservice', 'contacts': 'accounts/contacts', 'ledger-db': 'ledger/ledger-db', 'accounts-db': 'accounts/accounts-db', 'ledgerwriter': 'ledger/ledgerwriter', 'balancereader': 'ledger/balancereader', 'transactionhistory': 'ledger/transactionhistory'}
    for name, path in paths.items():
        kind = 'StatefulSet' if name.endswith('-db') else 'Deployment'
        container = manifests[(kind, name)]['spec']['template']['spec']['containers'][0]
        env = {}
        for ref in container.get('envFrom', []):
            env.update(maps[ref['configMapRef']['name']])
        env.update({e['name']: e['value'] for e in container.get('env', []) if 'value' in e})
        env.update(ENABLE_TRACING='false', ENABLE_METRICS='false', LOG_LEVEL='info', NAMESPACE='vigil')
        context = BANK / 'src' / path
        java = name in ['ledgerwriter', 'balancereader', 'transactionhistory']
        build = {'context': str(context), 'dockerfile': str(ROOT / 'deploy/oracle/Java.Dockerfile') if java else str(context / 'Dockerfile')}
        svc = {'build': build, 'image': 'vigil-local/' + name + ':arm64', 'restart': 'unless-stopped', 'environment': env, 'mem_limit': '512m' if java else {'frontend': '128m', 'userservice': '192m', 'contacts': '128m'}.get(name, '256m'), 'logging': {'driver': 'json-file', 'options': {'max-size': '5m', 'max-file': '2'}}}
        if name.endswith('-db'):
            svc['volumes'] = [name + ':/var/lib/postgresql/data']
            svc['healthcheck'] = {'test': ['CMD-SHELL', 'pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB'], 'interval': '10s', 'timeout': '5s', 'retries': 30}
        else:
            svc['volumes'] = [str(public) + ':/tmp/.ssh/publickey:ro']
            if name == 'userservice':
                svc['volumes'].append(str(private) + ':/tmp/.ssh/privatekey:ro')
            svc['healthcheck'] = {'test': ['CMD', 'curl', '-fsS', 'http://127.0.0.1:8080/ready'], 'interval': '15s', 'timeout': '10s', 'retries': 20, 'start_period': '120s'} if java else python_health.copy()
            db = 'accounts-db' if name in ['userservice', 'contacts'] else 'ledger-db'
            svc['depends_on'] = {db: {'condition': 'service_healthy'}}
            if java:
                svc['depends_on']['migrate'] = {'condition': 'service_completed_successfully'}
        if name == 'frontend':
            env.update(BANK_NAME='Vigil · Synthetic Banking Demo', SCHEME='https', PLATFORM='oracle', CLUSTER_NAME='Oracle Always Free ARM')
            svc['ports'] = ['127.0.0.1:8080:8080']
        services[name] = svc
    migration = list(yaml.safe_load_all((ROOT / 'vigil-system/genal_toolbox/ledger-migration.yaml').read_text()))[0]['data']['migration.sql']
    (state / 'migration.sql').write_text(migration)
    services['migrate'] = {'image': 'postgres:17-alpine', 'command': ['psql', '-v', 'ON_ERROR_STOP=1', '-f', '/migration.sql'], 'environment': {'PGHOST': 'ledger-db', 'PGDATABASE': 'postgresdb', 'PGUSER': 'admin', 'PGPASSWORD': credentials['ledger_password']}, 'volumes': [str(state / 'migration.sql') + ':/migration.sql:ro'], 'depends_on': {'ledger-db': {'condition': 'service_healthy'}}, 'mem_limit': '128m'}
    tools = yaml.safe_load((ROOT / 'vigil-system/genal_toolbox/tools.yaml').read_text())
    tools['sources']['ledger-db']['password'] = credentials['ledger_password']
    tools['sources']['accounts-db']['password'] = credentials['accounts_password']
    tools_file = state / 'tools.yaml'
    if tools_file.exists():
        tools_file.chmod(0o600)
    tools_file.write_text(yaml.safe_dump(tools, sort_keys=False))
    tools_file.chmod(0o444)
    services['genal-toolbox-service'] = {'image': 'us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:0.16.0', 'command': ['--tools-file', '/app/tools.yaml', '--address', '0.0.0.0'], 'volumes': [str(tools_file) + ':/app/tools.yaml:ro'], 'restart': 'unless-stopped', 'depends_on': {'migrate': {'condition': 'service_completed_successfully'}, 'accounts-db': {'condition': 'service_healthy'}}, 'mem_limit': '192m'}
    for short in ['orchestrator', 'investigation', 'actuator', 'transaction_monitor']:
        name = short.replace('_', '-') + '-agent'
        folder = ROOT / 'vigil-system' / (short + '_agent')
        env = {'GENAL_TOOLBOX_SERVICE_URL': 'http://genal-toolbox-service:5000'}
        if short == 'orchestrator':
            env.update(INVESTIGATION_AGENT_SERVICE_URL='http://investigation-agent:8000', ACTUATOR_AGENT_SERVICE_URL='http://actuator-agent:8000', RISK_SCORE_THRESHOLD='7')
        if short == 'transaction_monitor':
            env.update(ORCHESTRATOR_SERVICE_URL='http://orchestrator-agent:8000', POLL_INTERVAL='15', FRAUD_THRESHOLD='100000', MONITOR_STATE_PATH='/data/monitor.sqlite3')
        svc = {'profiles': ['agents'], 'build': {'context': str(folder if short == 'investigation' else ROOT), 'dockerfile': str(folder / 'Dockerfile')}, 'image': 'vigil-local/' + name + ':arm64', 'environment': env, 'env_file': [str(env_file)], 'restart': 'unless-stopped', 'depends_on': {'genal-toolbox-service': {'condition': 'service_started'}}, 'mem_limit': '768m' if short in ['investigation', 'orchestrator'] else '256m', 'logging': {'driver': 'json-file', 'options': {'max-size': '5m', 'max-file': '2'}}}
        if short == 'transaction_monitor':
            svc['volumes'] = ['monitor-state:/data']
            svc['depends_on']['orchestrator-agent'] = {'condition': 'service_healthy'}
        else:
            svc['healthcheck'] = {'test': ['CMD', 'python', '-c', "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=5)"], 'interval': '15s', 'timeout': '10s', 'retries': 12, 'start_period': '60s'}
        services[name] = svc
    (state / 'Caddyfile').write_text(f'{hostname} {{\n  reverse_proxy frontend:8080\n}}\n')
    services['web'] = {'image': 'caddy:2', 'restart': 'unless-stopped', 'ports': ['80:80', '443:443'], 'volumes': [str(state / 'Caddyfile') + ':/etc/caddy/Caddyfile:ro', 'caddy-data:/data', 'caddy-config:/config'], 'depends_on': {'frontend': {'condition': 'service_healthy'}}, 'mem_limit': '128m'}
    document = {'name': 'vigil', 'services': services, 'volumes': {name: {} for name in ['ledger-db', 'accounts-db', 'monitor-state', 'caddy-data', 'caddy-config']}}
    output = state / 'compose.json'
    output.write_text(json.dumps(document, indent=2))
    output.chmod(0o600)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--hostname', required=True)
    parser.add_argument('--gemini-key-file')
    args = parser.parse_args()
    print(prepare(args.state_dir, args.hostname, args.gemini_key_file))
