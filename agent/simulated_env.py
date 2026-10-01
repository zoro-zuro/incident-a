"""Deterministic simulated service state for the hackathon MVP."""

from copy import deepcopy


_INITIAL_STATE = {
    "payment-service": {
        "version": "v1.8",
        "previous_version": "v1.7",
        "status": "degraded",
        "error_rate": 38.2,
        "latency_ms": 2400,
        "deployment_minutes_ago": 4,
    },
    "checkout-service": {
        "version": "v2.4.1",
        "previous_version": "v2.4.0",
        "status": "degraded",
        "error_rate": 8.3,
        "latency_ms": 1800,
        "deployment_minutes_ago": 8,
    },
    "payment-gateway": {
        "version": "v3.2",
        "previous_version": "v3.1",
        "status": "degraded",
        "error_rate": 12.4,
        "latency_ms": 1900,
        "deployment_minutes_ago": 8,
    },
    "search-service": {
        "version": "v5.2",
        "previous_version": "v5.2",
        "status": "degraded",
        "error_rate": 0.5,
        "latency_ms": 4200,
        "deployment_minutes_ago": 120,
    },
}

_state = deepcopy(_INITIAL_STATE)


def reset_state() -> None:
    """Reset services to their initial demo conditions."""
    _state.clear()
    _state.update(deepcopy(_INITIAL_STATE))


def get_service_state(service: str) -> dict:
    return deepcopy(_state.get(service, {
        "version": "unknown",
        "previous_version": "unknown",
        "status": "unknown",
        "error_rate": 0.0,
        "latency_ms": 0.0,
        "deployment_minutes_ago": 999,
    }))


def get_service_health(services: list[str]) -> dict:
    return {service: get_service_state(service)["status"] for service in services}


def get_deployment_history(services: list[str]) -> dict:
    return {
        service: {
            "version": get_service_state(service)["version"],
            "previous_version": get_service_state(service)["previous_version"],
            "deployed_minutes_ago": get_service_state(service)["deployment_minutes_ago"],
        }
        for service in services
    }


def get_application_logs(service: str, time_window_minutes: int = 15) -> list[dict]:
    state = get_service_state(service)
    if service in {"payment-service", "checkout-service", "payment-gateway"} and state["status"] == "degraded":
        messages = [
            "database connection pool exhausted",
            "connection acquisition timeout",
            "upstream request returned 503 Service Unavailable",
        ]
    elif service == "search-service":
        messages = [
            "Elasticsearch shard rebalancing",
            "search latency above threshold",
        ]
    else:
        messages = [f"Service {service} health check failed"]

    return [
        {
            "timestamp": f"-{index + 1}m",
            "service": service,
            "level": "ERROR",
            "message": message,
            "trace_id": f"sim-{service}-{index}",
            "host": f"{service}-pod-1",
        }
        for index, message in enumerate(messages)
    ]


def get_service_metrics(service: str, time_window_minutes: int = 15) -> list[dict]:
    state = get_service_state(service)
    values = {
        "error_rate": (state["error_rate"], "%"),
        "latency_p99": (state["latency_ms"], "ms"),
        "db_pool_used": (48 if state["status"] == "degraded" else 12, "connections"),
        "db_pool_max": (50, "connections"),
    }
    return [
        {
            "metric": metric,
            "service": service,
            "latest_value": value,
            "unit": unit,
            "anomaly": metric in {"error_rate", "latency_p99", "db_pool_used"} and state["status"] == "degraded",
            "time_window_minutes": time_window_minutes,
        }
        for metric, (value, unit) in values.items()
    ]


def rollback_deployment(service: str) -> dict:
    state = _state.setdefault(service, get_service_state(service))
    old_version = state["version"]
    state["version"] = state["previous_version"]
    state["previous_version"] = old_version
    state["status"] = "healthy"
    state["error_rate"] = 0.3
    state["latency_ms"] = 180.0
    if service in {"payment-service", "checkout-service"}:
        dependent = "payment-gateway"
        if dependent in _state:
            _state[dependent]["status"] = "healthy"
            _state[dependent]["error_rate"] = 0.4
            _state[dependent]["latency_ms"] = 220.0
    return {
        "action": "rollback",
        "service": service,
        "success": True,
        "message": f"{service} rolled back to {state['version']}",
    }


def restart_service(service: str) -> dict:
    state = _state.setdefault(service, get_service_state(service))
    state["status"] = "healthy"
    state["error_rate"] = min(state["error_rate"], 0.5)
    state["latency_ms"] = min(state["latency_ms"], 250.0)
    return {
        "action": "restart",
        "service": service,
        "success": True,
        "message": f"{service} restarted in the simulated environment",
    }


def scale_service(service: str, replicas: int) -> dict:
    state = _state.setdefault(service, get_service_state(service))
    state["status"] = "healthy"
    state["error_rate"] = min(state["error_rate"], 0.8)
    return {
        "action": "scale",
        "service": service,
        "replicas": replicas,
        "success": True,
        "message": f"{service} scaled to {replicas} replicas",
    }


def verify_service_health(services: list[str]) -> dict:
    return get_service_health(services)


def verify_error_rate(services: list[str]) -> dict:
    return {
        service: get_service_state(service)["error_rate"]
        for service in services
    }
