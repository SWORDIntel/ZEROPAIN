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

from zeropain.security.cnsa import build_signature_envelope, verify_signature_envelope


def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def _utc_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


class ExperimentTracker:
    """Persist run configuration, metrics, artifacts, and audit trail."""

    def __init__(
        self, base_dir: str = "runs", run_id: Optional[str] = None, write_signature: bool = True
    ):
        self.base_dir = Path(base_dir)
        self.run_id = run_id or _utc_now().strftime("%Y%m%d-%H%M%S")
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
            "created_utc": _utc_iso(),
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
            "timestamp": _utc_iso(),
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
            "timestamp": _utc_iso(),
            "user": self._user_identity(),
            "details": details,
        }
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def verify_signature(self) -> Tuple[bool, str]:
        """Verify the stored CNSA 2.0 signature envelope for this run."""

        if not self.signature_path.exists():
            return False, "Signature file missing"

        try:
            with self.signature_path.open("r", encoding="utf-8") as f:
                stored = json.load(f)
        except json.JSONDecodeError:
            return False, "Signature file corrupted"

        current_digest = self._compute_digest()
        return verify_signature_envelope(
            stored=stored,
            current_digest=current_digest,
            legacy_digest=self._compute_legacy_digest,
        )

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
        signature = build_signature_envelope(
            digest=digest,
            scope="run_files_v2",
            run_id=self.run_id,
            signed_utc=_utc_iso(),
            signed_by=self._user_identity(),
        )
        self._write_json(self.signature_path, signature)

    def _compute_digest(self) -> str:
        hasher = hashlib.sha384()
        for path in self._signed_file_paths():
            relative = path.relative_to(self.run_dir).as_posix().encode("utf-8")
            hasher.update(relative)
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
            hasher.update(b"\0")
        return hasher.hexdigest()

    def _compute_legacy_digest(self) -> str:
        hasher = hashlib.sha384()
        for path in [
            self.meta_path,
            self.run_dir / "config.json",
            self.run_dir / "metrics.jsonl",
            self.audit_path,
        ]:
            if not path.exists():
                continue
            hasher.update(path.read_bytes())
        return hasher.hexdigest()

    def _signed_file_paths(self) -> list[Path]:
        ignored_dirs = {self.checkpoints_dir.resolve(), self.logs_dir.resolve()}
        paths = []
        for path in self.run_dir.rglob("*"):
            if not path.is_file() or path == self.signature_path:
                continue
            resolved_parent = path.parent.resolve()
            if any(resolved_parent == ignored or ignored in resolved_parent.parents for ignored in ignored_dirs):
                continue
            paths.append(path)
        return sorted(paths, key=lambda p: p.relative_to(self.run_dir).as_posix())

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
