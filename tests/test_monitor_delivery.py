"""Offline tests: no bank, Gemini, Kubernetes, or outbound API calls."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       'vigil-system/transaction_monitor_agent'))
from delivery_store import DeliveryStore
from agent import TransactionMonitorAgent
from a2a.types import (Message, TextPart, Role, SendMessageResponse,
                       SendMessageSuccessResponse, JSONRPCErrorResponse, JSONRPCError)


def transaction(tx_id='one', amount=1500, when='2026-10-22T10:00:00+00:00'):
    return {'transaction_id': tx_id, 'amount': amount, 'timestamp': when}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'state.sqlite3'
        self.store = DeliveryStore(self.path)

    def test_pending_survives_restart_and_duplicate_poll(self):
        tx = transaction()
        self.store.ingest([tx], 1000)
        restarted = DeliveryStore(self.path)
        restarted.ingest([tx], 1000)
        self.assertEqual(restarted.pending(), [tx])
        self.assertEqual(restarted.checkpoint, tx['timestamp'])

    def test_failed_attempt_remains_pending_then_success_is_deduplicated(self):
        self.store.ingest([transaction()], 1000)
        self.store.record_attempt('one', False, 'timeout')
        self.assertEqual(len(self.store.pending()), 1)
        self.store.record_attempt('one', True)
        self.store.ingest([transaction()], 1000)
        self.assertEqual(self.store.pending(), [])
        self.assertEqual(self.store.summary()['delivered'], 1)

    def test_later_transaction_at_same_timestamp_is_not_lost(self):
        self.store.ingest([transaction('one')], 1000)
        self.store.ingest([transaction('one'), transaction('two')], 1000)
        self.assertEqual(len(self.store.pending()), 2)

    def test_invalid_batch_does_not_advance_cursor_or_insert_partial_rows(self):
        before = self.store.checkpoint
        with self.assertRaises(ValueError):
            self.store.ingest([transaction(), transaction('bad', float('nan'))], 1000)
        self.assertEqual(self.store.checkpoint, before)
        self.assertEqual(self.store.pending(), [])

    def test_boundary_amount_is_ignored_and_utc_timestamp_is_normalized(self):
        self.store.ingest([transaction(amount=1000, when='2026-10-22T15:30:00+05:30')], 1000)
        self.assertEqual(self.store.summary()['ignored'], 1)
        self.assertEqual(self.store.checkpoint, '2026-10-22T10:00:00+00:00')

    def test_timestamp_without_timezone_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.ingest([transaction(when='2026-10-22T10:00:00')], 1000)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.dict('os.environ', {'MONITOR_STATE_PATH': str(Path(self.temp.name) / 'state.sqlite3')}):
            self.monitor = TransactionMonitorAgent()

    def test_retry_after_restart_without_refetching_old_transaction(self):
        self.monitor.get_new_transactions_via_genai_toolbox = Mock(return_value=[transaction()])
        self.monitor.alert_orchestrator = AsyncMock(return_value=False)
        asyncio.run(self.monitor.process_new_transactions())
        self.assertEqual(self.monitor.delivery_store.summary()['pending'], 1)
        with patch.dict('os.environ', {'MONITOR_STATE_PATH': str(Path(self.temp.name) / 'state.sqlite3')}):
            restarted = TransactionMonitorAgent()
        restarted.get_new_transactions_via_genai_toolbox = Mock(return_value=[])
        restarted.alert_orchestrator = AsyncMock(return_value=True)
        asyncio.run(restarted.process_new_transactions())
        restarted.alert_orchestrator.assert_awaited_once()
        self.assertEqual(restarted.delivery_store.summary()['delivered'], 1)

    def test_poll_failure_still_dispatches_pending_alerts(self):
        self.monitor.delivery_store.ingest([transaction()], 1000)
        self.monitor.get_new_transactions_via_genai_toolbox = Mock(side_effect=OSError('offline'))
        self.monitor.alert_orchestrator = AsyncMock(return_value=True)
        asyncio.run(self.monitor.process_new_transactions())
        self.assertEqual(self.monitor.delivery_store.summary()['delivered'], 1)

    def test_delivered_alert_not_resent_when_inclusive_query_repeats_it(self):
        self.monitor.get_new_transactions_via_genai_toolbox = Mock(return_value=[transaction()])
        self.monitor.alert_orchestrator = AsyncMock(return_value=True)
        asyncio.run(self.monitor.process_new_transactions())
        asyncio.run(self.monitor.process_new_transactions())
        self.monitor.alert_orchestrator.assert_awaited_once()

    def test_protocol_error_keeps_alert_pending(self):
        response = SendMessageResponse(root=JSONRPCErrorResponse(
            id=1, error=JSONRPCError(code=-32603, message='offline')))
        self.monitor.orchestrator_client = Mock(send_message=AsyncMock(return_value=response))
        self.assertFalse(asyncio.run(self.monitor.alert_orchestrator(transaction())))

    def test_success_response_uses_same_message_id_on_retry(self):
        message = Message(message_id='reply', role=Role.agent, parts=[TextPart(text='{"status": "completed"}')])
        response = SendMessageResponse(root=SendMessageSuccessResponse(id=1, result=message))
        send = AsyncMock(return_value=response)
        self.monitor.orchestrator_client = Mock(send_message=send)
        self.assertTrue(asyncio.run(self.monitor.alert_orchestrator(transaction())))
        self.assertTrue(asyncio.run(self.monitor.alert_orchestrator(transaction())))
        ids = [call.args[0].params.message.message_id for call in send.await_args_list]
        self.assertEqual(ids[0], ids[1])

    def test_application_error_in_success_envelope_is_retried(self):
        message = Message(message_id='reply', role=Role.agent,
                          parts=[TextPart(text='{"status": "error"}')])
        response = SendMessageResponse(root=SendMessageSuccessResponse(id=1, result=message))
        self.monitor.orchestrator_client = Mock(send_message=AsyncMock(return_value=response))
        self.assertFalse(asyncio.run(self.monitor.alert_orchestrator(transaction())))

    def test_toolbox_queries_include_timestamp_boundary(self):
        root = Path(__file__).resolve().parents[1] / 'vigil-system/genal_toolbox'
        for filename in ['tools.yaml', 'toolbox-configmap.yaml']:
            self.assertIn("WHERE timestamp >= ($1::timestamptz AT TIME ZONE 'UTC')", (root / filename).read_text())


if __name__ == '__main__':
    unittest.main()
