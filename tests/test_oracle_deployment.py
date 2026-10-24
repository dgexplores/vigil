"""Check Oracle deployment boundaries without accessing cloud accounts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('oracle_prepare', ROOT / 'deploy/oracle/prepare.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OracleDeploymentTests(unittest.TestCase):
    def test_persistent_private_services_and_idempotent_secrets(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            output = module.prepare(state, 'demo.example.com')
            before = (state / 'credentials.json').read_bytes()
            document = json.loads(output.read_text())
            services = document['services']
            for name in ['ledger-db', 'accounts-db', 'transaction-monitor-agent']:
                self.assertTrue(services[name]['volumes'])
                self.assertNotIn('ports', services[name])
            self.assertEqual(services['frontend']['ports'], ['127.0.0.1:8080:8080'])
            self.assertEqual(services['web']['ports'], ['80:80', '443:443'])
            for name in ['orchestrator-agent', 'investigation-agent', 'actuator-agent']:
                self.assertNotIn('ports', services[name])
            self.assertEqual(services['transaction-monitor-agent']['environment']['FRAUD_THRESHOLD'], '100000')
            self.assertEqual(services['orchestrator-agent']['profiles'], ['agents'])
            self.assertIn('migrate', services['ledgerwriter']['depends_on'])
            self.assertEqual(services['ledgerwriter']['hostname'], 'ledgerwriter-oracle')
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            (state / 'agents.env').write_text('GEMINI_API_KEY=disposable-test-value\nGEMINI_MODEL=test-model\n')
            module.prepare(state, 'demo.example.com')
            self.assertEqual((state / 'credentials.json').read_bytes(), before)
            self.assertIn('disposable-test-value', (state / 'agents.env').read_text())

    def test_rejects_state_inside_checkout_and_invalid_hostname(self):
        with self.assertRaises(ValueError):
            module.prepare(ROOT / 'private-state', 'demo.example.com')
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                module.prepare(temp, 'demo.example.com\nmalformed')

    def test_optional_portfolio_edge_survives_later_release_render(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / 'private-state'
            public = Path(temp).resolve() / 'public-sites'
            module.prepare(state, 'vigil.example.com', portfolio_dir=public)
            # A later CI release omits the option; it must preserve the live route.
            output = module.prepare(state, 'vigil.example.com')
            document = json.loads(output.read_text())
            self.assertTrue(document['networks']['portfolio-edge']['external'])
            self.assertEqual(document['services']['web']['networks'], ['default', 'portfolio-edge'])
            self.assertIn(str(public / 'www') + ':/srv/portfolio:ro', document['services']['web']['volumes'])
            self.assertIn('import /etc/caddy/sites/*.caddy', (state / 'Caddyfile').read_text())
            for name in ['ledger-db', 'accounts-db', 'orchestrator-agent', 'actuator-agent']:
                self.assertNotIn('networks', document['services'][name])
