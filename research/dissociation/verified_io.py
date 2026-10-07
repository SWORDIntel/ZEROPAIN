"""JSON writer with optional ECC-like shadow verification.

Normal mode: writes exactly the same pretty JSON payload as before.
Debug mode (ZEROPAIN_VERIFY=1): additionally checks the in-memory result, reads the
written file back, compares canonical digests, and appends a compact JSONL audit record.

The primary output is never modified to contain verification state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from research.dissociation.verification import digest, verify


Relation = Callable[[Any], tuple[bool, str] | bool]


def write_json(
    path: str | Path,
    payload: Any,
    *,
    label: str,
    relations: Sequence[Relation] = (),
    replay: Callable[[], Any] | None = None,
    independent: Callable[[Any], tuple[bool, str] | bool] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def file_roundtrip(value: Any) -> tuple[bool, str]:
        try:
            disk_value = json.loads(out.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"file round-trip read failed: {type(exc).__name__}: {exc}"

        if digest(disk_value) != digest(value):
            return False, "in-memory and written-file canonical digests differ"

        if independent is not None:
            result = independent(value)
            if isinstance(result, tuple):
                return result
            return bool(result), ""
        return True, ""

    replay_enabled = os.getenv("ZEROPAIN_VERIFY_REPLAY", "").strip().lower() in {
        "1", "true", "yes", "on",
    }

    verify(
        payload,
        label=label,
        relations=relations,
        replay=replay if replay_enabled else None,
        independent=file_roundtrip,
        metadata={
            "output_path": str(out),
            **dict(metadata or {}),
        },
    )
    return out
