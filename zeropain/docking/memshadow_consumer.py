"""
Stub consumer for docking.* topics.
Intended to be wired into the orchestrator/AI layer to rerank/alert.
"""
from __future__ import annotations

from typing import Dict, Any, List


class MemshadowConsumerStub:
    def subscribe(self, topic: str, handler):
        # In production, register handler with MEMSHADOW client
        return True


def rerank_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder: apply no-op rerank
    scores = payload.get("scores", [])
    return {
        "job_id": payload.get("job_id"),
        "type": "docking.rerank",
        "scores": scores,
        "notes": "noop rerank stub",
    }


def alert_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    telem = payload.get("telemetry", {})
    alerts: List[str] = []
    if telem.get("elapsed_sec", 0) > 600:
        alerts.append("slow_job")
    return {
        "job_id": payload.get("job_id"),
        "type": "docking.alert",
        "alerts": alerts,
    }

