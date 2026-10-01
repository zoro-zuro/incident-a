"""Human approval gate for simulated remediation."""

import os
import sys
import threading
import time
from typing import Optional, Dict, Any

# In-memory approval events for web/API integration
_pending_approvals: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def register_pending_approval(incident_id: str, action: str, service: str, confidence: float) -> threading.Event:
    """Register an approval request and return the threading.Event to wait on."""
    with _lock:
        evt = threading.Event()
        _pending_approvals[incident_id] = {
            "event": evt,
            "status": "pending",
            "action": action,
            "service": service,
            "confidence": confidence,
            "timestamp": time.time(),
        }
        return evt


def record_approval_decision(incident_id: str, decision: str) -> bool:
    """Resolve a pending approval with 'approved' or 'denied'."""
    with _lock:
        if incident_id in _pending_approvals:
            _pending_approvals[incident_id]["status"] = decision
            _pending_approvals[incident_id]["event"].set()
            return True
        # If exact id not found, resolve the most recent pending approval
        if _pending_approvals:
            latest_id = list(_pending_approvals.keys())[-1]
            _pending_approvals[latest_id]["status"] = decision
            _pending_approvals[latest_id]["event"].set()
            return True
        return False


def get_pending_approval(incident_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve pending approval metadata if present."""
    with _lock:
        return _pending_approvals.get(incident_id)


def request_approval(action: str, service: str, confidence: float, incident_id: Optional[str] = None) -> str:
    """Return approved, denied, or pending without executing an action."""
    mode = os.getenv("APPROVAL_MODE", "manual").lower()

    print("\n[APPROVAL] Remediation requires approval")
    print(f"   Action: {action} | Service: {service} | Confidence: {confidence:.0%}")

    if mode == "auto":
        print("   Approval: configured local demo approval")
        return "approved"
    if mode == "deny":
        print("   Approval: denied by configuration")
        return "denied"

    id_key = incident_id or f"inc-{int(time.time())}"
    evt = register_pending_approval(id_key, action, service, confidence)

    if not sys.stdin.isatty():
        print(f"   Approval: waiting for Web UI approval (incident: {id_key})...")
        # Wait up to 300 seconds for approval from Web UI
        signaled = evt.wait(timeout=300)
        with _lock:
            decision = _pending_approvals.get(id_key, {}).get("status", "pending")
        if signaled and decision in {"approved", "denied"}:
            print(f"   Approval received from Web UI: {decision}")
            return decision
        print("   Approval: timed out waiting for Web UI (pending)")
        return "pending"

    # Interactive terminal
    answer = input("   Approve simulated remediation? [y/N]: ").strip().lower()
    decision = "approved" if answer in {"y", "yes"} else "denied"
    record_approval_decision(id_key, decision)
    return decision

