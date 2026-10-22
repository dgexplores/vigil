"""Offline service contracts: real SDK/HTTP schemas with fake model/toolbox results."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[1] / 'vigil-system'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / name / 'agent.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


orchestrator = load('orchestrator_agent')
investigation = load('investigation_agent')
actuator = load('actuator_agent')


def case(account='a', score=8):
    return {'transaction_data': {'from_account_id': account}, 'fraud_analysis': {'risk_score': score, 'justification': 'test'}}


class FakeSessions:
    async def create_session(self, **kwargs):
        pass


class AnalysisRunner:
    app_name = 'test'

    def __init__(self, text):
        self.text = text

    async def run_async(self, **kwargs):
        yield SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text=self.text)]), is_final_response=lambda: True)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_risk_policy_rejects_missing_low_invalid_and_wrong_account(self):
        self.assertIsNotNone(orchestrator._prepare_actuator_payload({'account_id': 'a'})[1])
        for score in [2, True, float('nan'), 11]:
            token = orchestrator._request_state.set({'transaction': {'from_account_id': 'a'}, 'threshold': 7, 'case_file': case(score=score)})
            try:
                self.assertIsNotNone(orchestrator._prepare_actuator_payload({'account_id': 'a'})[1])
            finally:
                orchestrator._request_state.reset(token)
        token = orchestrator._request_state.set({'transaction': {'from_account_id': 'a'}, 'threshold': 7, 'case_file': case()})
        try:
            self.assertIsNotNone(orchestrator._prepare_actuator_payload({'account_id': 'b'})[1])
            self.assertEqual(orchestrator._prepare_actuator_payload({'account_id': 'a'})[0]['account_id'], 'a')
        finally:
            orchestrator._request_state.reset(token)

    async def test_concurrent_request_state_isolated(self):
        service = orchestrator.OrchestratorService.__new__(orchestrator.OrchestratorService)
        service.risk_threshold = 7

        async def process(transaction):
            orchestrator._request_state.get()['case_file'] = case(transaction['from_account_id'])
            await asyncio.sleep(0)
            return orchestrator._prepare_actuator_payload({})[0]['account_id']

        service._process_transaction_alert = process
        result = await asyncio.gather(*(service.process_transaction_alert({'from_account_id': a}) for a in ['a', 'b']))
        self.assertEqual(result, ['a', 'b'])
        self.assertIsNone(orchestrator._request_state.get())

    async def test_successful_actuation_cannot_repeat_in_same_request(self):
        token = orchestrator._request_state.set({'transaction': {'from_account_id': 'a'}, 'threshold': 7, 'case_file': case()})
        calls = []

        async def delegate(**kwargs):
            calls.append(kwargs)
            return {'data': {'status': 'success'}}

        try:
            with patch.object(orchestrator, '_delegate_via_a2a', delegate):
                self.assertTrue(orchestrator._actuation_succeeded(await orchestrator.delegate_to_actuator_agent({})))
                self.assertIn('error', await orchestrator.delegate_to_actuator_agent({}))
            self.assertEqual(len(calls), 1)
        finally:
            orchestrator._request_state.reset(token)
        self.assertFalse(orchestrator._actuation_succeeded({'data': {'status': 'error'}}))

    async def test_actuator_http_requires_confirmed_database_row(self):
        service = actuator.ActuatorService()
        actuator.actuator_service = service
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=actuator.app), base_url='http://test') as client:
            with patch.object(service, 'call_genai_toolbox_api', return_value={'result': []}):
                response = await client.post('/execute', json={'action': 'lock_account', 'account_id': 'a'})
                self.assertEqual(response.json()['status'], 'error')
            with patch.object(service, 'call_genai_toolbox_api', return_value={'result': [{'account_id': 'a'}]}) as invoke:
                response = await client.post('/execute', json={'action': 'lock_account', 'account_id': 'a'})
                self.assertEqual(response.json()['status'], 'success')
                invoke.assert_called_once_with('lock_account', {'account_id': 'a'})

    async def test_investigation_validates_model_output_and_context_failure(self):
        service = investigation.InvestigationService.__new__(investigation.InvestigationService)
        service.session_service = FakeSessions()
        service.default_user_id = 'test'
        with patch.object(service, 'call_genai_toolbox_api', return_value=[]):
            for text in ['{"risk_score": 8, "justification": "unusual"}', '{"risk_score": 99, "justification": "bad"}', '[]', '{"risk_score": true, "justification": "bad"}', 'not-json']:
                service.runner = AnalysisRunner(text)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=investigation.app), base_url='http://test') as client:
                    investigation.investigation_service = service
                    result = (await client.post('/investigate', json={'from_account_id': 'a'})).json()
                self.assertEqual('fraud_analysis' in result, '"unusual"' in text)
        with patch.object(service, 'call_genai_toolbox_api', side_effect=RuntimeError('unavailable')):
            result = await service.investigate_transaction({'from_account_id': 'a'})
            self.assertIn('Failed to gather context', result['error'])

    async def test_toolbox_response_parser_fails_on_error_envelopes(self):
        service = investigation.InvestigationService.__new__(investigation.InvestigationService)
        service.genal_toolbox_url = 'http://toolbox'
        for data in [{'error': 'permission denied'}, {'result': 'not-json'}]:
            response = SimpleNamespace(status_code=200, json=lambda: data)
            with patch.object(investigation.requests, 'post', return_value=response):
                with self.assertRaises(ValueError):
                    service.call_genai_toolbox_api('lookup', {})
        response = SimpleNamespace(status_code=200, json=lambda: {'result': '[{"account_id":"a"}]'})
        with patch.object(investigation.requests, 'post', return_value=response):
            self.assertEqual(service.call_genai_toolbox_api('lookup', {}), [{'account_id': 'a'}])

    async def test_delegated_investigation_uses_original_transaction(self):
        original = {'from_account_id': 'a', 'amount': 100}
        token = orchestrator._request_state.set({'transaction': original, 'threshold': 7})
        calls = []

        async def delegate(**kwargs):
            calls.append(kwargs['payload'])
            return {'data': case()}

        try:
            with patch.object(orchestrator, '_delegate_via_a2a', delegate):
                await orchestrator.delegate_to_investigation_agent({'from_account_id': 'a', 'amount': 999999})
            self.assertEqual(calls, [original])
        finally:
            orchestrator._request_state.reset(token)

    async def test_orchestrator_http_flow_high_low_and_failed_actuation(self):
        for score, lock_status in [(8, 'success'), (2, 'success'), (8, 'error')]:
            service = orchestrator.OrchestratorService.__new__(orchestrator.OrchestratorService)
            service.risk_threshold = 7
            service.default_user_id = 'test'
            service.session_service = FakeSessions()
            delegated = []

            async def delegate(**kwargs):
                delegated.append(kwargs['agent_label'])
                if kwargs['agent_label'] == 'InvestigationAgent':
                    return {'data': case(score=score)}
                return {'data': {'status': lock_status}}

            class Runner:
                app_name = 'test'

                async def run_async(self, **kwargs):
                    result = await orchestrator.delegate_to_investigation_agent({'from_account_id': 'a'})
                    responses = [SimpleNamespace(name='delegate_to_investigation_agent', response=result)]
                    if score < 7:
                        blocked = await orchestrator.delegate_to_actuator_agent({'account_id': 'a'})
                        responses.append(SimpleNamespace(name='delegate_to_actuator_agent', response=blocked))
                    yield SimpleNamespace(content=None, get_function_calls=lambda: [], get_function_responses=lambda: responses, is_final_response=lambda: False)

            service.runner = Runner()
            orchestrator.orchestrator_service = service
            body = {'jsonrpc': '2.0', 'id': 'one', 'method': 'message/send', 'params': {'message': {'messageId': 'm', 'role': 'user', 'parts': [{'kind': 'text', 'text': 'Process transaction alert:{"from_account_id":"a"}'}]}}}
            with patch.object(orchestrator, '_delegate_via_a2a', delegate):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=orchestrator.app), base_url='http://test') as client:
                    response = await client.post('/', json=body)
            self.assertEqual(response.status_code, 200)
            import json
            result = json.loads(response.json()['result']['parts'][0]['text'].split(':', 1)[1])
            self.assertEqual(result['status'], 'error' if score >= 7 and lock_status == 'error' else 'completed')
            self.assertEqual(result['should_actuate'], score >= 7 and lock_status == 'success')
            self.assertEqual('ActuatorAgent' in delegated, score >= 7)
            self.assertIsNone(orchestrator._request_state.get())

    async def test_monitor_accepts_actual_orchestrator_ack_and_retries_app_errors(self):
        import sys
        import tempfile
        from unittest.mock import AsyncMock
        sys.path.insert(0, str(ROOT / 'transaction_monitor_agent'))
        import agent as monitor_module
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict('os.environ', {'MONITOR_STATE_PATH': str(Path(tmp) / 'outbox.sqlite3')}):
                monitor = monitor_module.TransactionMonitorAgent()
            service = SimpleNamespace(process_transaction_alert=AsyncMock(return_value={'status': 'completed'}))
            orchestrator.orchestrator_service = service
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=orchestrator.app), base_url='http://test') as http:
                monitor.orchestrator_client = monitor_module.A2AClient(httpx_client=http, url='http://test/')
                tx = {'transaction_id': 'test', 'from_account_id': 'a'}
                self.assertTrue(await monitor.alert_orchestrator(tx))
                service.process_transaction_alert.return_value = {'status': 'error'}
                self.assertFalse(await monitor.alert_orchestrator(tx))

    async def test_real_a2a_request_response_contracts(self):
        body = {'jsonrpc': '2.0', 'id': 'one', 'method': 'message/send', 'params': {'message': {'messageId': 'm', 'role': 'user', 'parts': [{'kind': 'text', 'text': 'execute_action:{"action":"lock_account","account_id":"a"}'}]}}}
        actuator.actuator_service = actuator.ActuatorService()
        with patch.object(actuator.actuator_service, 'call_genai_toolbox_api', return_value={'result': [{'account_id': 'a'}]}):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=actuator.app), base_url='http://test') as client:
                result = await client.post('/', json=body)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['id'], 'one')
        self.assertIn('"status": "success"', result.json()['result']['parts'][0]['text'])


if __name__ == '__main__':
    unittest.main()
