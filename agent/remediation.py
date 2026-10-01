"""Stateful simulated remediation for the hackathon MVP.

These functions intentionally never execute shell commands, kubectl, or
external infrastructure actions. They mutate agent.simulated_env only.
"""

import os
import time
import random
from datetime import datetime
from typing import Optional

from agent.simulated_env import (
    rollback_deployment as simulate_rollback,
    restart_service as simulate_restart,
    scale_service as simulate_scale,
)


# ── Confidence threshold for auto-remediation ──────────────
AUTO_REMEDIATE_THRESHOLD = 0.92   # below this → escalate instead



def restart_service(
    service: str,
    namespace: str = "default",
    reason: str = "",
) -> dict:
    """Update the service in the local simulated environment."""

    print(f"   🔄 restart_service({service}) — simulated")
    return simulate_restart(service)



def rollback_deployment(
    service: str,
    namespace: str = "default",
    revision: Optional[int] = None,
) -> dict:
    """Roll back the service in the local simulated environment."""

    revision_str = f" to revision {revision}" if revision else " to previous version"
    print(f"   ⏪ rollback_deployment({service}{revision_str}) — simulated")
    return simulate_rollback(service)



def scale_pods(
    service: str,
    replicas: int,
    namespace: str = "default",
) -> dict:
    """Scale the service in the local simulated environment."""

    print(f"   📈 scale_pods({service}, replicas={replicas}) — simulated")
    return simulate_scale(service, replicas)



def clear_cache(
    service: str,
    cache_type: str = "redis",
    pattern: str = "*",
) -> dict:
    """Record a cache operation without touching external Redis."""

    print(f"   🧹 clear_cache({service}, pattern={pattern})")

    return {
        "action": "clear_cache",
        "service": service,
        "cache_type": cache_type,
        "keys_cleared": 0,
        "success": True,
        "message": "Cache clear simulated; no external cache was modified",
    }


# Maps root cause keywords → remediation action
REMEDIATION_RULES = [
    {
        "keywords":  ["connection pool", "pool exhausted", "pool timeout"],
        "action":    "rollback_deployment",
        "reason":    "Pool exhaustion usually caused by bad deploy — rollback first",
        "fallback":  "restart_service",
    },
    {
        "keywords":  ["redis", "econnrefused", "session store", "cache"],
        "action":    "restart_service",
        "target":    "redis",
        "reason":    "Redis connection failure — restart Redis pod",
    },
    {
        "keywords":  ["memory", "oom", "oomkilled", "heap"],
        "action":    "restart_service",
        "reason":    "Memory leak — restart buys time, then investigate",
    },
    {
        "keywords":  ["traffic", "spike", "capacity", "overload", "saturation"],
        "action":    "scale_pods",
        "replicas":  6,
        "reason":    "Traffic spike — scale out immediately",
    },
    {
        "keywords":  ["deployment", "deploy", "version", "rollout", "release"],
        "action":    "rollback_deployment",
        "reason":    "Issue correlates with recent deployment",
    },
    {
        "keywords":  ["cache", "stale", "evict"],
        "action":    "clear_cache",
        "reason":    "Cache corruption or memory pressure",
    },
]


def plan_remediation(root_cause: str, services: list) -> dict:
    """
    Match root cause to the best remediation action.
    Returns the plan — does NOT execute it yet.
    """
    root_lower = root_cause.lower()

    for rule in REMEDIATION_RULES:
        if any(kw in root_lower for kw in rule["keywords"]):
            return {
                "action":   rule["action"],
                "service":  rule.get("target", services[0] if services else "unknown"),
                "reason":   rule["reason"],
                "replicas": rule.get("replicas", 4),
                "matched":  True,
            }

    # No rule matched
    return {
        "action":  "escalate",
        "service": services[0] if services else "unknown",
        "reason":  "No automated remediation rule matched — escalating to human",
        "matched": False,
    }


def execute_remediation(plan: dict) -> dict:
    """
    Execute the remediation plan and return the result.
    """
    action  = plan["action"]
    service = plan["service"]

    if action == "restart_service":
        return restart_service(service, reason=plan.get("reason", ""))

    elif action == "rollback_deployment":
        return rollback_deployment(service)

    elif action == "scale_pods":
        return scale_pods(service, replicas=plan.get("replicas", 4))

    elif action == "clear_cache":
        return clear_cache(service)

    else:
        return {
            "action":  "escalate",
            "service": service,
            "success": False,
            "message": plan.get("reason", "Manual intervention required"),
        }