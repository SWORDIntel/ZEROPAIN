from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def stable_hash(payload: Any, algorithm: str = "sha384") -> str:
    hasher = hashlib.new(algorithm)
    hasher.update(canonical_json_bytes(payload))
    return hasher.hexdigest()
