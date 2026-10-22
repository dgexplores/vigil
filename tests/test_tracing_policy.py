"""Remote trace headers must not reach ADK's constrained propagation parser."""
import importlib.util
import os
from pathlib import Path
import unittest

class TracingPolicyTest(unittest.TestCase):
    def test_untrusted_trace_context_is_not_propagated(self):
        source = Path(__file__).resolve().parents[1] / 'vigil-system/orchestrator_agent/agent.py'
        spec = importlib.util.spec_from_file_location('tracing_policy_orchestrator', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from opentelemetry import propagate, trace
        context = propagate.extract({
            'traceparent': '00-12345678901234567890123456789012-1234567890123456-01',
            'tracestate': 'a=b' + ' ' * 100000 + 'x',
        })
        self.assertEqual(os.environ['OTEL_PROPAGATORS'], 'none')
        self.assertFalse(trace.get_current_span(context).get_span_context().is_valid)
