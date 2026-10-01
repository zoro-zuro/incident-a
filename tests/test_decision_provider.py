"""Unit and integration tests for DecisionProvider, Mock, Laya, and Groq providers."""

import os
import io
import sys
import json
import unittest
from unittest.mock import MagicMock, patch

# Enable HuggingFace offline mode for tests using local cache
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Reconfigure stdout/stderr to UTF-8 so emoji print statements in graph.py
# don't fail on Windows cp1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from agent.decision_provider import (
    DecisionProvider,
    MockDecisionProvider,
    LayaDecisionProvider,
    GroqDecisionProvider,
    get_decision_provider,
    ALLOWED_ACTIONS,
)
from agent.state import IncidentState
from agent.graph import build_graph


class TestDecisionProviders(unittest.TestCase):
    def setUp(self):
        self.sample_state = {
            "alert": {
                "title": "High error rate on checkout-service",
                "service": "checkout-service",
                "metric": "error_rate",
                "value": "8.3%",
                "threshold": "1%",
                "environment": "production",
                "triggered_at": "2026-10-01T00:00:00Z",
                "runbook_hint": "db_connection_pool",
            },
            "severity": "P1",
            "affected_services": ["checkout-service"],
            "logs": [
                {"timestamp": "-1m", "service": "checkout-service", "level": "ERROR", "message": "database connection pool exhausted"},
            ],
            "metrics": [
                {"metric": "error_rate", "service": "checkout-service", "latest_value": 8.3, "unit": "%", "anomaly": True},
            ],
            "service_health": {"checkout-service": "degraded"},
            "deployment_history": {
                "checkout-service": {"version": "v2.4.1", "previous_version": "v2.4.0", "deployed_minutes_ago": 8}
            },
            "runbook_title": "Database Connection Pool Exhaustion",
            "runbook_content": "Rollback deployment if error rate spiked immediately following a rollout.",
            "similar_past_incidents": [],
            "ticket_id": "INC-TEST-1",
        }

    # ─────────────────────────────────────────────────────────────
    # Test 1: Mock Provider
    # ─────────────────────────────────────────────────────────────
    def test_mock_provider(self):
        with patch.dict(os.environ, {"DECISION_PROVIDER": "mock"}):
            provider = get_decision_provider()
            self.assertIsInstance(provider, MockDecisionProvider)

            result = provider.evaluate_incident(self.sample_state)
            self.assertIn("hypothesis", result)
            self.assertIn("root_cause", result)
            self.assertIn("recommended_action", result)
            self.assertIn("confidence", result)
            self.assertIn(result["recommended_action"], ALLOWED_ACTIONS)
            self.assertGreaterEqual(result["confidence"], 0.0)
            self.assertLessEqual(result["confidence"], 1.0)

    # ─────────────────────────────────────────────────────────────
    # Test 2: Laya Provider Interface Preservation (Isolated)
    # ─────────────────────────────────────────────────────────────
    @patch("agent.decision_provider._load_laya")
    def test_laya_provider_interface(self, mock_load_laya):
        self.assertTrue(issubclass(LayaDecisionProvider, DecisionProvider))

        mock_agent = MagicMock()
        mock_agent.predict.return_value = [{
            "answers": {
                "severity": {"choice": "P1"},
                "deployment_hypothesis": {"noul": 0.95},
                "database_failure_hypothesis": {"noul": 0.10},
                "sufficient_evidence": {"noul": 0.90},
                "recommended_action": {"choice": "rollback", "answer_confidence": 0.92},
            }
        }]
        mock_load_laya.return_value = mock_agent

        with patch.dict(os.environ, {"DECISION_PROVIDER": "laya"}):
            try:
                provider = get_decision_provider()
                self.assertIsInstance(provider, LayaDecisionProvider)
                result = provider.evaluate_incident(self.sample_state)
                self.assertEqual(result["recommended_action"], "rollback")
                self.assertEqual(result["confidence"], 0.92)
            except RuntimeError as exc:
                # If optional laya package is not installed in the active python env
                self.assertIn("Install optional Laya support", str(exc))

    # ─────────────────────────────────────────────────────────────
    # Test 3: Groq Provider Schema & Normalization
    # ─────────────────────────────────────────────────────────────
    @patch("groq.Groq")
    def test_groq_provider_valid_schema(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client

        groq_json_response = json.dumps({
            "severity": "P1",
            "hypothesis": "Database connection pool exhausted after v2.4.1 rollout",
            "root_cause": "Deployment v2.4.1 unindexed query exhausted the connection pool",
            "recommended_action": "rollback",
            "confidence": 0.95,
            "sufficient_evidence": True,
            "deployment_hypothesis_probability": 0.96,
            "database_failure_probability": 0.04,
            "reason": "Clear correlation with recent release and pool exhaustion errors",
            "requires_approval": True,
        })

        mock_choice = MagicMock()
        mock_choice.message.content = groq_json_response
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_fake_key_12345", "DECISION_PROVIDER": "groq"}):
            provider = get_decision_provider()
            self.assertIsInstance(provider, GroqDecisionProvider)

            result = provider.evaluate_incident(self.sample_state)
            self.assertEqual(result["recommended_action"], "rollback")
            self.assertEqual(result["confidence"], 0.95)
            self.assertEqual(result["severity"], "P1")
            self.assertTrue(result["sufficient_evidence"])
            self.assertTrue(result["requires_approval"])
            self.assertIn("Database connection pool exhausted", result["hypothesis"])
            self.assertIn("deployment_hypothesis", result)
            self.assertIn("database_failure_hypothesis", result)
            self.assertEqual(result["provider"], "groq")

    # ─────────────────────────────────────────────────────────────
    # Test 4: Invalid / Malformed Groq Response Rejection
    # ─────────────────────────────────────────────────────────────
    @patch("groq.Groq")
    def test_groq_invalid_json_rejected(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Not valid JSON {"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_fake_key_12345"}):
            provider = GroqDecisionProvider()
            with self.assertRaises(RuntimeError) as ctx:
                provider.evaluate_incident(self.sample_state)
            self.assertIn("model returned invalid JSON", str(ctx.exception))

    @patch("groq.Groq")
    def test_groq_unauthorized_action_rejected(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client

        groq_json_response = json.dumps({
            "severity": "P1",
            "hypothesis": "Unknown error",
            "root_cause": "Unknown",
            "recommended_action": "kubectl_delete_all_pods",  # Disallowed
            "confidence": 0.99,
        })
        mock_choice = MagicMock()
        mock_choice.message.content = groq_json_response
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_fake_key_12345"}):
            provider = GroqDecisionProvider()
            with self.assertRaises(RuntimeError) as ctx:
                provider.evaluate_incident(self.sample_state)
            self.assertIn("not in allowed actions", str(ctx.exception))

    @patch("groq.Groq")
    def test_groq_missing_fields_rejected(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client

        groq_json_response = json.dumps({
            "hypothesis": "Missing recommended action and confidence",
        })
        mock_choice = MagicMock()
        mock_choice.message.content = groq_json_response
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_fake_key_12345"}):
            provider = GroqDecisionProvider()
            with self.assertRaises(RuntimeError) as ctx:
                provider.evaluate_incident(self.sample_state)
            self.assertIn("Missing fields", str(ctx.exception))

    # ─────────────────────────────────────────────────────────────
    # Test 5: Missing API Key Clear Error
    # ─────────────────────────────────────────────────────────────
    def test_groq_missing_api_key(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=False):
            if "GROQ_API_KEY" in os.environ:
                del os.environ["GROQ_API_KEY"]
            with self.assertRaises(RuntimeError) as ctx:
                GroqDecisionProvider()
            self.assertIn("GROQ_API_KEY is missing", str(ctx.exception))

    # ─────────────────────────────────────────────────────────────
    # Test 6: No Silent Fallback from Groq to Mock
    # ─────────────────────────────────────────────────────────────
    @patch("groq.Groq")
    def test_no_silent_fallback_on_api_error(self, mock_groq_cls):
        from groq import APIConnectionError

        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APIConnectionError(request=MagicMock())

        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_fake_key_12345", "DECISION_PROVIDER": "groq"}):
            provider = get_decision_provider()
            with self.assertRaises(RuntimeError) as ctx:
                provider.evaluate_incident(self.sample_state)
            self.assertIn("connection/timeout error", str(ctx.exception))

    # ─────────────────────────────────────────────────────────────
    # Test 7: Provider Selection Dispatch
    # ─────────────────────────────────────────────────────────────
    def test_provider_selection_dispatch(self):
        with patch.dict(os.environ, {"DECISION_PROVIDER": "unknown_provider"}):
            with self.assertRaises(ValueError) as ctx:
                get_decision_provider()
            self.assertIn("Supported providers are: 'groq', 'laya', 'mock'", str(ctx.exception))

    # ─────────────────────────────────────────────────────────────
    # Test 8: Full LangGraph Integration with GroqDecisionProvider
    # ─────────────────────────────────────────────────────────────
    @patch("groq.Groq")
    def test_full_langgraph_workflow_with_groq(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client

        groq_json_response = json.dumps({
            "severity": "P1",
            "hypothesis": "Database connection pool exhaustion on checkout-service caused by deployment v2.4.1",
            "root_cause": "Deployment v2.4.1 introduced unindexed query holding connections open",
            "recommended_action": "rollback",
            "confidence": 0.95,
            "sufficient_evidence": True,
            "deployment_hypothesis_probability": 0.96,
            "database_failure_probability": 0.05,
            "reason": "Direct evidence of pool exhaustion coinciding with deployment",
            "requires_approval": True,
        })
        mock_choice = MagicMock()
        mock_choice.message.content = groq_json_response
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        env_overrides = {
            "DECISION_PROVIDER": "groq",
            "GROQ_API_KEY": "gsk_test_fake_key_12345",
            "APPROVAL_MODE": "auto",
            "USE_MOCK_LLM": "1",
            "LANGCHAIN_TRACING_V2": "false",
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PYTHONUTF8": "1",
        }

        with patch.dict(os.environ, env_overrides):
            from agent.simulated_env import reset_state
            reset_state()

            app = build_graph()
            initial_state = IncidentState(
                alert=self.sample_state["alert"],
                logs=[],
                metrics=[],
                service_health={},
                deployment_history={},
                runbook_title="",
                runbook_content="",
                root_cause="",
                hypothesis="",
                confidence=0.0,
                confidence_history=[],
                severity="P1",
                affected_services=[],
                team_paged="",
                slack_thread="",
                ticket_id="INC-UNIT-TEST-GROQ",
                incident_report="",
                status="investigating",
                needs_escalation=False,
                retry_count=0,
                max_retries=3,
                remediation_attempted=False,
                remediation_result="",
                similar_past_incidents=[],
                decision={},
                approval_status="pending",
                verification={},
            )

            config = {"configurable": {"thread_id": "test-groq-thread"}}
            result = app.invoke(initial_state, config=config)

            # Assert complete pipeline verification
            self.assertEqual(result["decision"]["provider"], "groq")
            self.assertEqual(result["decision"]["recommended_action"], "rollback")
            self.assertEqual(result["approval_status"], "approved")
            self.assertTrue(result["remediation_attempted"])
            self.assertIn("rolled back", result["remediation_result"].lower())
            self.assertIn("resolved", result["status"])
            self.assertIn("# Incident Report", result["incident_report"])
            self.assertIn("checkout-service", result["incident_report"])


if __name__ == "__main__":
    unittest.main()
