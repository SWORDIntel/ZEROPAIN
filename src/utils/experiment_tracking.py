"""Experiment tracker with audit logging and tamper-evident signatures."""

from __future__ import annotations

import datetime as _dt
import getpass
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class ExperimentTracker:
    """Persist run configuration, metrics, artifacts, and audit trail."""

    def __init__(
        self, base_dir: str = "runs", run_id: Optional[str] = None, write_signature: bool = True
    ):
        self.base_dir = Path(base_dir)
        self.run_id = run_id or _dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        self.run_dir = self.base_dir / self.run_id
        self.checkpoints_dir = self.run_dir / "checkpoints"
        self.logs_dir = self.run_dir / "logs"
        self.audit_path = self.run_dir / "audit.jsonl"
        self.signature_path = self.run_dir / "signature.sha384"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.meta_path = self.run_dir / "metadata.json"
        if not self.meta_path.exists():
            self._write_json(self.meta_path, self._default_metadata())
            self.append_audit_event("run_created", {"run_id": self.run_id})
        if write_signature:
            self._refresh_signature()

    def _default_metadata(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_utc": _dt.datetime.utcnow().isoformat() + "Z",
            "executed_by": self._user_identity(),
            "git_commit": self._git_commit(),
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        }

    def record_config(self, config: Dict[str, Any]) -> None:
        config_path = self.run_dir / "config.json"
        merged = {"config": config, **self._default_metadata()}
        self._write_json(config_path, merged)
        self.append_audit_event("config_recorded", {"keys": sorted(config.keys())})
        self._refresh_signature()

    def upsert_metadata(self, extra: Dict[str, Any]) -> None:
        base = self._default_metadata()
        if self.meta_path.exists():
            try:
                with self.meta_path.open("r", encoding="utf-8") as f:
                    current = json.load(f)
                base.update(current)
            except json.JSONDecodeError:
                pass
        base.update(extra)
        self._write_json(self.meta_path, base)
        self.append_audit_event("metadata_updated", extra)
        self._refresh_signature()

    def log_metrics(self, stage: str, metrics: Dict[str, Any]) -> None:
        metrics_path = self.run_dir / "metrics.jsonl"
        payload = {
            "stage": stage,
            "timestamp": _dt.datetime.utcnow().isoformat() + "Z",
            "metrics": metrics,
        }
        with metrics_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
        self.append_audit_event("metrics_logged", {"stage": stage})
        self._refresh_signature()

    def log_artifact(self, name: str, content: Dict[str, Any]) -> Path:
        artifact_path = self.run_dir / name
        self._write_json(artifact_path, content)
        self.append_audit_event("artifact_logged", {"artifact": name})
        self._refresh_signature()
        return artifact_path

    def read_audit_events(self) -> list:
        if not self.audit_path.exists():
            return []
        events = []
        with self.audit_path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events

    def append_audit_event(self, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        details = details or {}
        event = {
            "action": action,
            "timestamp": _dt.datetime.utcnow().isoformat() + "Z",
            "user": self._user_identity(),
            "details": details,
        }
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def verify_signature(self) -> Tuple[bool, str]:
        """Verify the stored SHA-384 signature for this run."""

        if not self.signature_path.exists():
            return False, "Signature file missing"

        try:
            with self.signature_path.open("r", encoding="utf-8") as f:
                stored = json.load(f)
            digest = stored.get("digest")
            signed_by = stored.get("signed_by", "unknown")
        except json.JSONDecodeError:
            return False, "Signature file corrupted"

        current_digest = self._compute_digest()
        if digest != current_digest:
            return False, f"Signature mismatch (signed by {signed_by})"
        return True, f"Signature valid (signed by {signed_by})"

    @classmethod
    def verify_signature_for_run(cls, run_dir: Path) -> Tuple[bool, str]:
        tracker = cls(base_dir=str(run_dir.parent), run_id=run_dir.name, write_signature=False)
        return tracker.verify_signature()

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def _refresh_signature(self, write: bool = True) -> None:
        digest = self._compute_digest()
        if not write:
            return
        signature = {
            "digest": digest,
            "algorithm": "sha384",
            "run_id": self.run_id,
            "signed_utc": _dt.datetime.utcnow().isoformat() + "Z",
            "signed_by": self._user_identity(),
        }
        self._write_json(self.signature_path, signature)

    def _compute_digest(self) -> str:
        hasher = hashlib.sha384()
        for path in [self.meta_path, self.run_dir / "config.json", self.run_dir / "metrics.jsonl", self.audit_path]:
            if not path.exists():
                continue
            hasher.update(path.read_bytes())
        return hasher.hexdigest()

    def _git_commit(self) -> str:
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
                .decode()
                .strip()
            )
        except Exception:
            return "unknown"

    def _user_identity(self) -> str:
        return os.environ.get("ZP_USER") or getpass.getuser() or "unknown"


__all__ = ["ExperimentTracker"]
