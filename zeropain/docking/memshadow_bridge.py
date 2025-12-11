"""
MEMSHADOW bridge for ZeroPain docking artifacts.
Publishes docking meta, scores, telemetry, and feedback as structured records.
If memshadow protocol/client is unavailable, falls back to a no-op stub.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Iterable

import requests  # type: ignore


def _ensure_protocol_on_path() -> None:
    # Try libs/memshadow-protocol/python
    for root in [Path.cwd(), *Path(__file__).resolve().parents]:
        candidate = root / "libs" / "memshadow-protocol" / "python"
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            return
    # Fallback: extract memshadow_protocol.zip to temp
    zip_path = Path.cwd() / "memshadow-protocol.zip"
    if zip_path.exists():
        tmpdir = Path(tempfile.mkdtemp(prefix="memshadow_protocol_"))
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)
        py_dir = tmpdir / "python"
        if py_dir.exists() and str(py_dir) not in sys.path:
            sys.path.insert(0, str(py_dir))


class MemshadowClient:
    """HTTP client that packages payloads using memshadow-protocol."""

    def __init__(self, url: str, token: Optional[str] = None, priority: str = "normal"):
        _ensure_protocol_on_path()
        try:
            from dsmil_protocol import MemshadowMessage, MessageType, Priority  # type: ignore
        except Exception as exc:
            raise ImportError("memshadow-protocol not available") from exc

        self.MemshadowMessage = MemshadowMessage
        self.MessageType = MessageType
        self.Priority = Priority
        self.url = url
        self.token = token
        self.priority = getattr(self.Priority, priority.upper(), self.Priority.NORMAL)

    def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        envelope = {
            "topic": topic,
            "payload": payload,
        }
        blob = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        message = self.MemshadowMessage(
            msg_type=self.MessageType.INTEL_REPORT,
            priority=self.priority,
            payload=blob,
        )
        data = message.pack()

        headers = {"Content-Type": "application/octet-stream"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        resp = requests.post(self.url, data=data, headers=headers, timeout=10)
        resp.raise_for_status()
        return True


class MemshadowClientStub:
    """Fallback stub when memshadow protocol or endpoint is unavailable."""

    def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        return True


def _load_json(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        with path.open("r") as f:
            return json.load(f)
    except Exception:
        return None


def _iter_scores(scores_path: Path) -> List[Dict[str, Any]]:
    scores_records: List[Dict[str, Any]] = []
    if scores_path.exists():
        import csv

        with scores_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                scores_records.append(row)
    return scores_records


def _get_client(cfg: Optional[Dict[str, Any]] = None):
    cfg = cfg or {}
    url = cfg.get("MEMSHADOW_URL") or os.environ.get("MEMSHADOW_URL")
    token = cfg.get("MEMSHADOW_TOKEN") or os.environ.get("MEMSHADOW_TOKEN")
    priority = cfg.get("MEMSHADOW_PRIORITY") or os.environ.get("MEMSHADOW_PRIORITY", "normal")
    if url:
        try:
            return MemshadowClient(url=url, token=token, priority=priority)
        except Exception:
            return MemshadowClientStub()
    return MemshadowClientStub()


def publish_docking_run(
    job_id: str,
    run_dir: Path,
    memshadow_client=None,
    sign: bool = False,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Publish docking artifacts to MEMSHADOW.
    Expects run_dir/runs/<job_id>/docking/{inputs/manifest.json, scores.csv, telemetry.json}.
    """
    client = memshadow_client or _get_client(cfg)
    docking_dir = run_dir / job_id / "docking"
    telemetry = _load_json(docking_dir / "telemetry.json") or {}
    inputs = _load_json(docking_dir / "inputs" / "manifest.json") or {}
    scores_records = _iter_scores(docking_dir / "scores.csv")

    meta_payload = {
        "job_id": job_id,
        "type": "docking.meta",
        "inputs": inputs,
        "telemetry": telemetry,
        "sign": sign,
    }
    scores_payload = {
        "job_id": job_id,
        "type": "docking.scores",
        "scores": scores_records,
        "sign": sign,
    }

    client.publish(f"docking.{job_id}.meta", meta_payload)
    client.publish(f"docking.{job_id}.scores", scores_payload)

    return {"meta": meta_payload, "scores": scores_payload}


def publish_feedback(
    job_id: str,
    feedback_entry: Dict[str, Any],
    memshadow_client=None,
    sign: bool = False,
    cfg: Optional[Dict[str, Any]] = None,
) -> bool:
    client = memshadow_client or _get_client(cfg)
    payload = {
        "job_id": job_id,
        "type": "docking.feedback",
        "feedback": feedback_entry,
        "sign": sign,
    }
    return client.publish(f"docking.{job_id}.feedback", payload)


def publish_telemetry(
    job_id: str,
    phase: str,
    telemetry: Dict[str, Any],
    memshadow_client=None,
    sign: bool = False,
    cfg: Optional[Dict[str, Any]] = None,
) -> bool:
    client = memshadow_client or _get_client(cfg)
    payload = {
        "job_id": job_id,
        "type": "docking.telemetry",
        "phase": phase,  # start|progress|end
        "telemetry": telemetry,
        "sign": sign,
    }
    return client.publish(f"docking.{job_id}.telemetry", payload)

