"""Check real bank service readiness and ledger enforcement without LLM calls."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import subprocess
import time
import urllib.request
import urllib.error
import urllib.parse


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verify(compose, timeout=300):
    command = ['docker', 'compose', '-f', str(compose)]
    services = ['ledger-db', 'accounts-db', 'userservice', 'contacts', 'ledgerwriter', 'balancereader', 'transactionhistory', 'frontend', 'genal-toolbox-service']
    deadline = time.monotonic() + timeout
    while True:
        waiting = []
        for service in services:
            ident = subprocess.check_output(command + ['ps', '-q', service], text=True).strip()
            if not ident:
                waiting.append(service)
                continue
            state = json.loads(subprocess.check_output(['docker', 'inspect', ident], text=True))[0]['State']
            if state['Status'] != 'running' or state.get('Health', {}).get('Status', 'healthy') != 'healthy':
                waiting.append(service)
        if not waiting:
            break
        if time.monotonic() > deadline:
            raise RuntimeError('Services not ready: ' + ', '.join(waiting))
        time.sleep(5)
    with urllib.request.urlopen('http://127.0.0.1:8080/ready', timeout=10) as response:
        assert response.status == 200
    # Exercise the UI -> userservice -> JWT -> balance/history routes using only
    # the upstream fictional demo account. Never print its session cookie.
    cookies = http.cookiejar.CookieJar()
    browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies), NoRedirect())
    form = urllib.parse.urlencode({'username': 'testuser', 'password': 'bankofanthos'}).encode()
    try:
        browser.open('http://127.0.0.1:8080/login', data=form, timeout=30)
        raise RuntimeError('Expected login redirect')
    except urllib.error.HTTPError as response:
        if response.code != 302 or urllib.parse.urlparse(response.headers.get('Location', '')).path != '/home':
            raise RuntimeError('Demo login failed') from None
    if not list(cookies):
        raise RuntimeError('Demo login did not create a session')
    with browser.open('http://127.0.0.1:8080/home', timeout=30) as response:
        if response.status != 200 or b'Current Balance' not in response.read():
            raise RuntimeError('Authenticated bank home did not render')
    # Everything is rolled back, including the synthetic lock and probe transfer.
    sql = """BEGIN;
INSERT INTO vigil_account_locks(account_id) VALUES ('9999999001') ON CONFLICT DO NOTHING;
DO $$ BEGIN
  BEGIN
    INSERT INTO transactions(from_acct,to_acct,from_route,to_route,amount,timestamp)
    VALUES ('9999999001','9999999002','883745000','883745000',100,NOW());
    RAISE EXCEPTION 'Vigil lock enforcement failed';
  EXCEPTION WHEN check_violation THEN
    NULL;
  END;
END $$;
ROLLBACK;
"""
    subprocess.run(command + ['exec', '-T', 'ledger-db', 'psql', '-U', 'admin', '-d', 'postgresdb', '-v', 'ON_ERROR_STOP=1'], input=sql, text=True, check=True, capture_output=True)
    print('PASS: bank readiness, demo login/home routing, actual PostgreSQL lock enforcement, and rollback of test data')
    print('Live Gemini investigation is a separate required release check.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    verify(args.compose, args.timeout)
