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
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            module.prepare(state, 'demo.example.com')
            self.assertEqual((state / 'credentials.json').read_bytes(), before)

    def test_rejects_state_inside_checkout_and_invalid_hostname(self):
        with self.assertRaises(ValueError):
            module.prepare(ROOT / 'private-state', 'demo.example.com')
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                module.prepare(temp, 'demo.example.com\nmalformed')
