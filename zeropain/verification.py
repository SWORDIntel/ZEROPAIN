"""ECC-like shadow verification for ZeroPain outputs.

A cryptographic digest detects result mutation/corruption. It does NOT prove the
calculation is correct. Correctness checking therefore uses a syndrome made from
orthogonal check bits:

bit 0  SERIALIZATION  canonical result can be serialized and re-hashed
bit 1  FINITE         no unexpected NaN/Inf values
bit 2  RANGE          declared probabilities/rates stay in [0,1]
bit 3  RELATION       supplied cross-field invariants hold
bit 4  REPLAY         deterministic replay matches the original result
bit 5  INDEPENDENT    optional independent checker agrees
bit 6  STORAGE        written result/file round-trip agrees

A zero syndrome means "all enabled checks passed", not "scientifically true".

By default this module is silent. Enable with:
    ZEROPAIN_VERIFY=1

Optional:
    ZEROPAIN_VERIFY_LOG=/path/to/verification.jsonl
    ZEROPAIN_VERIFY_STRICT=1   # raise on non-zero syndrome

The audit log intentionally stores result hashes/check summaries rather than full
payloads, so normal result files remain the source of truth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntFlag
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Callable, Iterable, Mapping, Sequence


class CheckBit(IntFlag):
    SERIALIZATION = 1 << 0
    FINITE = 1 << 1
    RANGE = 1 << 2
    RELATION = 1 << 3
    REPLAY = 1 << 4
    INDEPENDENT = 1 << 5
    STORAGE = 1 << 6


@dataclass(frozen=True)
class CheckResult:
    bit: int
    name: str
    enabled: bool
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class VerificationRecord:
    schema_version: int
    timestamp_unix: float
    label: str
    digest_sha256: str
    syndrome: int
    passed: bool
    checks: tuple[CheckResult, ...]
    metadata: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["checks"] = [asdict(check) for check in self.checks]
        return result


def enabled() -> bool:
    return os.getenv("ZEROPAIN_VERIFY", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def strict_enabled() -> bool:
    return os.getenv("ZEROPAIN_VERIFY_STRICT", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        ensure_ascii=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _walk_numbers(value: Any, path: str = "$") -> Iterable[tuple[str, float]]:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        yield path, float(value)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk_numbers(item, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _walk_numbers(item, f"{path}[{index}]")


def finite_check(value: Any) -> tuple[bool, str]:
    bad = [path for path, number in _walk_numbers(value) if not math.isfinite(number)]
    return (not bad, "" if not bad else f"non-finite values at {bad[:8]}")


def probability_range_check(
    value: Any,
    *,
    field_tokens: Sequence[str] = (
        "probability",
        "accuracy",
        "consistency",
        "trust",
    ),
) -> tuple[bool, str]:
    """Conservative heuristic: inspect only semantically bounded field names.

    Generic words such as "rate" and "fraction" are intentionally excluded because
    they may mean sampling_rate_hz, a signed fractional improvement, etc. Runners
    should add explicit relation checks for additional bounded quantities.
    """

    bad: list[str] = []

    def visit(item: Any, path: str = "$", field_name: str = "") -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                visit(child, f"{path}.{key}", str(key).lower())
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]", field_name)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            if any(token in field_name for token in field_tokens):
                number = float(item)
                if math.isfinite(number) and not 0.0 <= number <= 1.0:
                    bad.append(f"{path}={number}")

    visit(value)
    return (not bad, "" if not bad else f"out-of-range fields: {bad[:8]}")


def relation_check(
    value: Any,
    relations: Sequence[Callable[[Any], tuple[bool, str] | bool]],
) -> tuple[bool, str]:
    failures = []
    for index, relation in enumerate(relations):
        result = relation(value)
        if isinstance(result, tuple):
            passed, detail = result
        else:
            passed, detail = bool(result), ""
        if not passed:
            failures.append(detail or f"relation[{index}] failed")
    return (not failures, "; ".join(failures[:8]))


def replay_check(
    value: Any,
    replay: Callable[[], Any] | None,
) -> tuple[bool, str]:
    if replay is None:
        return True, "disabled"
    other = replay()
    first = digest(value)
    second = digest(other)
    return (
        first == second,
        "" if first == second else f"digest mismatch {first[:12]} != {second[:12]}",
    )


def independent_check(
    value: Any,
    checker: Callable[[Any], tuple[bool, str] | bool] | None,
) -> tuple[bool, str]:
    if checker is None:
        return True, "disabled"
    result = checker(value)
    return result if isinstance(result, tuple) else (bool(result), "")


def _log_path() -> Path:
    return Path(os.getenv("ZEROPAIN_VERIFY_LOG", "runs/verification.jsonl"))


def append_record(record: VerificationRecord) -> None:
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")


def verify(
    value: Any,
    *,
    label: str,
    relations: Sequence[Callable[[Any], tuple[bool, str] | bool]] = (),
    replay: Callable[[], Any] | None = None,
    independent: Callable[[Any], tuple[bool, str] | bool] | None = None,
    storage: Callable[[Any], tuple[bool, str] | bool] | None = None,
    metadata: Mapping[str, Any] | None = None,
    force: bool = False,
) -> VerificationRecord | None:
    """Run silent shadow verification and append one compact audit record.

    Returns None when verification is disabled. On pass: no stdout/stderr.
    On failure: record is written first; strict mode then raises RuntimeError.
    """

    if not (force or enabled()):
        return None

    checks: list[CheckResult] = []
    syndrome = 0

    def run(bit: CheckBit, name: str, fn: Callable[[], tuple[bool, str]], *, enabled_: bool = True):
        nonlocal syndrome
        if not enabled_:
            checks.append(CheckResult(int(bit), name, False, True, "disabled"))
            return
        try:
            passed, detail = fn()
        except Exception as exc:  # verifier failure itself is a failed check
            passed, detail = False, f"{type(exc).__name__}: {exc}"
        if not passed:
            syndrome |= int(bit)
        checks.append(CheckResult(int(bit), name, True, passed, detail))

    # Serialization is both the result-integrity parity and a precondition for audit.
    result_digest = ""
    try:
        result_digest = digest(value)
        serialization = (True, "")
    except Exception as exc:
        serialization = (False, f"{type(exc).__name__}: {exc}")
        # Stable placeholder digest for the failed record.
        result_digest = hashlib.sha256(repr(value).encode("utf-8")).hexdigest()

    run(CheckBit.SERIALIZATION, "canonical_serialization", lambda: serialization)
    run(CheckBit.FINITE, "finite_values", lambda: finite_check(value))
    run(CheckBit.RANGE, "probability_ranges", lambda: probability_range_check(value))
    run(
        CheckBit.RELATION,
        "cross_field_relations",
        lambda: relation_check(value, relations),
        enabled_=bool(relations),
    )
    run(
        CheckBit.REPLAY,
        "deterministic_replay",
        lambda: replay_check(value, replay),
        enabled_=replay is not None,
    )
    run(
        CheckBit.INDEPENDENT,
        "independent_checker",
        lambda: independent_check(value, independent),
        enabled_=independent is not None,
    )
    run(
        CheckBit.STORAGE,
        "storage_roundtrip",
        lambda: independent_check(value, storage),
        enabled_=storage is not None,
    )

    record = VerificationRecord(
        schema_version=1,
        timestamp_unix=time.time(),
        label=label,
        digest_sha256=result_digest,
        syndrome=syndrome,
        passed=syndrome == 0,
        checks=tuple(checks),
        metadata=dict(metadata or {}),
    )
    append_record(record)

    if syndrome and strict_enabled():
        failed = [check.name for check in checks if check.enabled and not check.passed]
        raise RuntimeError(
            f"shadow verification failed for {label}: syndrome=0x{syndrome:02x}; "
            f"checks={','.join(failed)}"
        )
    return record


# Reusable ECC-like invariants for common result schemas.

def relation_count_not_exceed_total(
    count_field: str,
    total_field: str,
) -> Callable[[Any], tuple[bool, str]]:
    def check(value: Any) -> tuple[bool, str]:
        if not isinstance(value, Mapping):
            return False, "payload is not a mapping"
        count = value.get(count_field)
        total = value.get(total_field)
        if count is None or total is None:
            return True, "fields absent"
        passed = 0 <= float(count) <= float(total)
        return passed, "" if passed else f"{count_field}={count} > {total_field}={total}"
    return check


def relation_sum_close(
    fields: Sequence[str],
    total: float = 1.0,
    tolerance: float = 1e-6,
) -> Callable[[Any], tuple[bool, str]]:
    def check(value: Any) -> tuple[bool, str]:
        if not isinstance(value, Mapping):
            return False, "payload is not a mapping"
        if any(field not in value for field in fields):
            return True, "fields absent"
        actual = sum(float(value[field]) for field in fields)
        passed = abs(actual - total) <= tolerance
        return passed, "" if passed else f"sum({fields})={actual}, expected {total}"
    return check
