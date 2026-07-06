"""QIHSE persistence bridge for ZeroPain job and run records."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from .backends import database_backend_status


class QihseRecordStore:
    """Small JSON record store backed by QIHSE KV and document APIs."""

    def __init__(self, path: str | None = None):
        _prepare_qihse_import_path()
        import qihse

        self.path = Path(path or os.getenv("QIHSE_DB_PATH", "runs/qihse_backend.kv"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._kv = qihse.KVStore()
        if self.path.exists():
            self._kv.load(str(self.path))
        self._doc = qihse.DocumentStore(self._kv)

    def close(self) -> None:
        self._doc.close()
        self._kv.close()

    def put_json(self, namespace: str, key: str, payload: Dict[str, Any]) -> None:
        record_key = f"{namespace}:{key}"
        encoded = json.dumps(payload, sort_keys=True, default=str)
        if not self._kv.set(record_key, encoded):
            raise RuntimeError(f"QIHSE KV write failed for {record_key}")
        self._doc.insert_json(_document_id(record_key), encoded)
        self._kv.save(str(self.path))


def mirror_database_record(namespace: str, key: str, payload: Dict[str, Any]) -> bool:
    """Mirror a JSON record into QIHSE when that backend is explicitly selected."""

    status = database_backend_status()
    if status.backend != "qihse":
        return False
    if not status.available:
        raise RuntimeError(status.message)

    store = QihseRecordStore()
    try:
        store.put_json(namespace, key, payload)
    finally:
        store.close()
    return True


def _document_id(key: str) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _prepare_qihse_import_path() -> None:
    status = database_backend_status()
    if not status.qihse_home:
        return
    python_path = Path(status.qihse_home) / "python"
    if python_path.exists():
        python_path_text = str(python_path)
        if python_path_text not in sys.path:
            sys.path.insert(0, python_path_text)
