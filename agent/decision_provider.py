"""Structured incident decisions behind a single provider boundary."""

import json
import os
from functools import lru_cache


class DecisionProvider:
    def evaluate_incident(self, state: dict) -> dict:
        raise NotImplementedError


class MockDecisionProvider(DecisionProvider):
    """Deterministic decision model for local demos and tests."""

    def evaluate_incident(self, state: dict) -> dict:
        alert = state.get("alert", {})
        services = state.get("affected_services", [])
        service = services[0] if services else alert.get("service", "unknown")
        logs = " ".join(item.get("message", "") for item in state.get("logs", []))
        deployment = state.get("deployment_history", {}).get(service, {})
        metrics = state.get("metrics", [])
        error_rate = next(
            (item.get("latest_value", 0) for item in metrics if item.get("metric") == "error_rate"),
            0,
        )
        deployment_related = "pool" in logs.lower() and deployment.get("deployed_minutes_ago", 999) <= 15
        action = "rollback" if deployment_related else "investigate_more"
        confidence = 0.94 if action == "rollback" else 0.58
        if error_rate and float(error_rate) >= 10:
            confidence = min(0.96, confidence + 0.03)

        return {
            "severity": alert.get("severity", state.get("severity", "P1")),
            "deployment_hypothesis": {"yes": 0.93 if deployment_related else 0.25, "no": 0.07 if deployment_related else 0.75},
            "database_failure_hypothesis": {"yes": 0.18, "no": 0.82},
            "sufficient_evidence": confidence >= 0.85,
            "recommended_action": action,
            "confidence": confidence,
            "hypothesis": f"Recent deployment of {service} caused database connection pool exhaustion",
            "root_cause": f"Deployment {deployment.get('version', 'unknown')} correlates with connection pool exhaustion on {service}; database health is simulated as healthy.",
            "needs_more_evidence": confidence < 0.85,
        }


class LayaDecisionProvider(DecisionProvider):
    """Optional Laya typed-decision provider.

    Laya is loaded only when DECISION_PROVIDER=laya. The rest of the graph
    depends on this interface, not on the Laya package directly.
    """

    def __init__(self, model_name: str = "convaiinnovations/laya-typed-decisions"):
        try:
            import laya
            import torch
        except ImportError as exc:
            raise RuntimeError("Install optional Laya support with: pip install laya") from exc
        thread_count = int(os.getenv("LAYA_TORCH_THREADS", "0"))
        if thread_count > 0:
            torch.set_num_threads(thread_count)
        self.agent = _load_laya(laya, model_name)

    def evaluate_incident(self, state: dict) -> dict:
        questions = {
            "severity": {
                "type": "choice",
                "criteria": ["P0", "P1", "P2", "P3"],
                "instructions": "Choose the incident severity from the evidence.",
            },
            "deployment_hypothesis": {
                "type": "noul",
                "instructions": "Is the recent deployment the most likely primary cause?",
            },
            "database_failure_hypothesis": {
                "type": "noul",
                "instructions": "Does the evidence indicate database infrastructure is the primary cause?",
            },
            "sufficient_evidence": {
                "type": "noul",
                "instructions": "Is there sufficient evidence to recommend remediation?",
            },
            "recommended_action": {
                "type": "choice",
                "criteria": ["rollback", "restart", "scale", "investigate_more", "no_action"],
                "instructions": "Choose the remediation best supported by the evidence.",
            },
        }
        predict_kwargs = {}
        if os.getenv("LAYA_MAX_LEN"):
            predict_kwargs["max_len"] = int(os.environ["LAYA_MAX_LEN"])
        if os.getenv("LAYA_HEAD_MAX_LEN"):
            predict_kwargs["head_max_len"] = int(os.environ["LAYA_HEAD_MAX_LEN"])
        result = self.agent.predict(_structured_state(state), questions, **predict_kwargs)
        return _normalize_laya_result(result, state)


@lru_cache(maxsize=1)
def _load_laya(laya_module, model_name: str):
    return laya_module.load(model_name)


def _structured_state(state: dict) -> dict:
    return {
        "incident": {
            "alert": state.get("alert", {}),
            "severity": state.get("severity"),
            "services": state.get("affected_services", []),
        },
        "logs": state.get("logs", [])[-12:],
        "metrics": state.get("metrics", [])[-16:],
        "service_health": state.get("service_health", {}),
        "deployment": state.get("deployment_history", {}),
        "historical_incidents": state.get("similar_past_incidents", []),
        "runbook": {
            "title": state.get("runbook_title", ""),
            "content": state.get("runbook_content", "")[:4000],
        },
    }


def _normalize_laya_result(result, state: dict) -> dict:
    if hasattr(result, "model_dump"):
        result = result.model_dump()
    if isinstance(result, list):
        result = result[0] if result else {}
    if isinstance(result, dict) and isinstance(result.get("answers"), dict):
        result = result["answers"]
    if not isinstance(result, dict):
        result = json.loads(result)

    severity_answer = result.get("severity", {})
    deployment_answer = result.get("deployment_hypothesis", {})
    database_answer = result.get("database_failure_hypothesis", {})
    evidence_answer = result.get("sufficient_evidence", {})
    action_answer = result.get("recommended_action", {})

    deployment_probability = float(deployment_answer.get("noul", 0.0))
    database_probability = float(database_answer.get("noul", 0.0))
    sufficient_evidence = float(evidence_answer.get("noul", 0.0)) >= 0.5
    action = action_answer.get("choice", "investigate_more")
    confidence = float(action_answer.get(
        "answer_confidence",
        action_answer.get("confidence", 0.0),
    ))
    service = (state.get("affected_services") or [state.get("alert", {}).get("service", "unknown")])[0]

    return {
        "severity": severity_answer.get("choice", state.get("severity", "P1")),
        "deployment_hypothesis": {"yes": deployment_probability, "no": 1 - deployment_probability},
        "database_failure_hypothesis": {"yes": database_probability, "no": 1 - database_probability},
        "sufficient_evidence": sufficient_evidence,
        "recommended_action": action,
        "confidence": confidence,
        "hypothesis": f"Laya selected {action} for {service} with deployment probability {deployment_probability:.0%}",
        "root_cause": f"Structured Laya decision for {service}; deployment hypothesis probability {deployment_probability:.0%}, database failure probability {database_probability:.0%}.",
        "needs_more_evidence": not sufficient_evidence,
        "raw_answers": result,
    }


ALLOWED_ACTIONS = ["rollback", "restart", "scale", "clear_cache", "investigate_more", "no_action"]


def _sanitize_text(val: str) -> str:
    """Strip obvious tokens, passwords, or secret indicators."""
    import re
    return re.sub(
        r'(?i)(api[_-]?key|token|password|secret|bearer\s+)[:=]\s*["\']?[^"\'\s,;]+["\']?',
        r'\1=[REDACTED]',
        str(val),
    )


def _build_groq_incident_context(state: dict) -> dict:
    alert = state.get("alert", {})
    services = state.get("affected_services", [])
    service = services[0] if services else alert.get("service", "unknown")
    deployment_history = state.get("deployment_history", {})
    service_health = state.get("service_health", {})

    metrics = state.get("metrics", [])
    recent_metrics = []
    for m in metrics[-16:]:
        recent_metrics.append({
            "service": m.get("service"),
            "metric": m.get("metric"),
            "latest_value": m.get("latest_value"),
            "unit": m.get("unit"),
            "anomaly": m.get("anomaly", False),
        })

    logs = state.get("logs", [])
    recent_logs = []
    for l in logs[-12:]:
        recent_logs.append({
            "timestamp": l.get("timestamp"),
            "service": l.get("service"),
            "level": l.get("level"),
            "message": _sanitize_text(l.get("message", "")),
        })

    similar = []
    for inc in state.get("similar_past_incidents", [])[:3]:
        similar.append({
            "incident_id": inc.get("incident_id"),
            "title": _sanitize_text(inc.get("title", "")),
            "root_cause": _sanitize_text(inc.get("root_cause", "")),
            "resolution": inc.get("resolution"),
            "similarity": inc.get("similarity"),
        })

    runbook_title = state.get("runbook_title", "")
    runbook_content = state.get("runbook_content", "")[:3000]

    return {
        "incident_id": state.get("ticket_id") or "INC-CURRENT",
        "service": service,
        "affected_services": services,
        "alert": {
            "title": _sanitize_text(alert.get("title", "")),
            "metric": alert.get("metric", ""),
            "value": alert.get("value", ""),
            "threshold": alert.get("threshold", ""),
            "environment": alert.get("environment", "production"),
            "triggered_at": alert.get("triggered_at", ""),
            "runbook_hint": alert.get("runbook_hint", ""),
        },
        "severity": state.get("severity", "P1"),
        "service_health": service_health,
        "deployment_history": deployment_history,
        "recent_metrics": recent_metrics,
        "recent_logs": recent_logs,
        "retrieved_runbook": {
            "title": runbook_title,
            "guidance_excerpt": runbook_content,
        },
        "retrieved_similar_incidents": similar,
    }


class GroqDecisionProvider(DecisionProvider):
    """Real Groq Cloud LLM decision provider using structured output.

    Used when DECISION_PROVIDER=groq. Groq acts purely as a structured decision
    engine and cannot execute shell/kubectl or bypass human approval.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key or not self.api_key.strip():
            raise RuntimeError(
                "GroqDecisionProvider failed: GROQ_API_KEY is missing. "
                "Set GROQ_API_KEY in your environment or .env file."
            )

        self.model_name = model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        raw_timeout = timeout or os.getenv("GROQ_TIMEOUT_SECONDS", "20.0")
        try:
            self.timeout = float(raw_timeout)
        except (ValueError, TypeError):
            self.timeout = 20.0

        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key, timeout=self.timeout)
        except ImportError as exc:
            raise RuntimeError(
                "GroqDecisionProvider failed: Groq SDK not installed. Run: pip install groq"
            ) from exc

    def evaluate_incident(self, state: dict) -> dict:
        print(f"   [decision] Using GroqDecisionProvider (model: {self.model_name})")
        context = _build_groq_incident_context(state)
        service = context["service"]

        system_prompt = (
            "You are an SRE incident decision support component in an automated on-call system.\n"
            "Your task is to analyze the incident evidence, retrieved runbook guidance, and past incident memory "
            "to produce a structured incident decision.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. You are a DECISION SUPPORT COMPONENT only. You DO NOT execute actions.\n"
            "2. Never claim an action has been executed or that a rollback occurred or that verification succeeded.\n"
            "3. Do not invent metrics, logs, or deployment history.\n"
            "4. Execution of any remediation requires human approval.\n"
            "5. The recommended_action MUST be exactly one of: ['rollback', 'restart', 'scale', 'clear_cache', 'investigate_more', 'no_action'].\n"
            "   - Choose 'rollback' if the incident correlates directly with a recent deployment and connection pool exhaustion/regression.\n"
            "   - Choose 'restart' for memory leaks/OOM or simple transient lockups.\n"
            "   - Choose 'scale' for capacity/traffic saturation spikes.\n"
            "   - Choose 'clear_cache' for cache corruption or key explosions.\n"
            "   - Choose 'investigate_more' or 'no_action' if evidence is insufficient or ambiguous.\n"
            "6. Set confidence as a float between 0.0 and 1.0 (e.g. 0.95 if evidence is definitive and aligns with runbook).\n"
            "7. Output valid JSON ONLY matching the required schema.\n"
        )

        user_prompt = (
            f"Analyze this incident context and return your structured decision:\n\n"
            f"{json.dumps(context, indent=2)}\n\n"
            "Required JSON schema:\n"
            "{\n"
            '  "severity": "P0|P1|P2|P3",\n'
            '  "hypothesis": "Concise single-sentence hypothesis of what failed and why",\n'
            '  "root_cause": "Detailed technical root cause citing evidence (e.g. deployment version, metrics, logs)",\n'
            '  "recommended_action": "rollback|restart|scale|clear_cache|investigate_more|no_action",\n'
            '  "confidence": 0.95,\n'
            '  "sufficient_evidence": true,\n'
            '  "deployment_hypothesis_probability": 0.95,\n'
            '  "database_failure_probability": 0.10,\n'
            '  "reason": "Brief technical justification for the recommended action",\n'
            '  "requires_approval": true\n'
            "}"
        )

        print(f"   [decision] Sending incident context for {service} to Groq API...")

        try:
            from groq import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                timeout=self.timeout,
            )
            print("   [decision] Received response from Groq API")
        except AuthenticationError as exc:
            raise RuntimeError(f"GroqDecisionProvider authentication failed: {exc}") from exc
        except RateLimitError as exc:
            raise RuntimeError(f"GroqDecisionProvider rate limit exceeded: {exc}") from exc
        except APIConnectionError as exc:
            raise RuntimeError(f"GroqDecisionProvider connection/timeout error: {exc}") from exc
        except APIStatusError as exc:
            raise RuntimeError(f"GroqDecisionProvider API error (status {exc.status_code}): {exc.message}") from exc
        except Exception as exc:
            raise RuntimeError(f"GroqDecisionProvider unexpected error: {exc}") from exc

        content = response.choices[0].message.content
        return self._validate_and_normalize(content, state)

    def _validate_and_normalize(self, raw_content: str, state: dict) -> dict:
        try:
            parsed = json.loads(raw_content)
        except Exception as exc:
            raise RuntimeError(f"GroqDecisionProvider failed: model returned invalid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError("GroqDecisionProvider failed: model response is not a JSON object")

        required_fields = ["hypothesis", "root_cause", "recommended_action", "confidence"]
        missing = [f for f in required_fields if f not in parsed]
        if missing:
            raise RuntimeError(
                f"GroqDecisionProvider failed: model returned an invalid decision schema. Missing fields: {missing}"
            )

        action = str(parsed["recommended_action"]).lower().strip()
        allowed = set(ALLOWED_ACTIONS)
        if action not in allowed:
            raise RuntimeError(
                f"GroqDecisionProvider failed: recommended_action '{action}' is not in allowed actions: {list(allowed)}"
            )

        try:
            confidence = max(0.0, min(1.0, float(parsed["confidence"])))
        except (ValueError, TypeError) as exc:
            raise RuntimeError(f"GroqDecisionProvider failed: invalid confidence value: {exc}") from exc

        deployment_prob = float(parsed.get("deployment_hypothesis_probability", 0.9 if action == "rollback" else 0.2))
        deployment_prob = max(0.0, min(1.0, deployment_prob))

        db_prob = float(parsed.get("database_failure_probability", 0.1))
        db_prob = max(0.0, min(1.0, db_prob))

        sufficient = bool(parsed.get("sufficient_evidence", confidence >= 0.85))

        print(f"   [decision] Validated structured decision: action={action}, confidence={confidence:.0%}")

        return {
            "severity": parsed.get("severity", state.get("severity", "P1")),
            "deployment_hypothesis": {"yes": deployment_prob, "no": round(1.0 - deployment_prob, 4)},
            "database_failure_hypothesis": {"yes": db_prob, "no": round(1.0 - db_prob, 4)},
            "sufficient_evidence": sufficient,
            "recommended_action": action,
            "confidence": confidence,
            "hypothesis": parsed["hypothesis"],
            "root_cause": parsed["root_cause"],
            "needs_more_evidence": not sufficient,
            "requires_approval": True,
            "provider": "groq",
            "model": self.model_name,
            "reason": parsed.get("reason", ""),
            "raw_decision": parsed,
        }


def get_decision_provider() -> DecisionProvider:
    provider = os.getenv("DECISION_PROVIDER", "mock").lower().strip()
    if provider == "groq":
        return GroqDecisionProvider()
    elif provider == "laya":
        return LayaDecisionProvider()
    elif provider == "mock":
        return MockDecisionProvider()
    else:
        raise ValueError(
            f"Unknown DECISION_PROVIDER: '{provider}'. Supported providers are: 'groq', 'laya', 'mock'."
        )
