"""Scrub previously verified result files against their audit digests.

This is analogous to an ECC memory scrub: it does not recompute scientific truth,
but it detects result-file mutation/corruption after the original verified write.

Exit status:
  0 all referenced files match
  1 at least one mismatch/missing/unreadable file

Default is quiet on success.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.dissociation.verification import digest


def scrub(log_path: str | Path) -> dict:
    path = Path(log_path)
    if not path.exists():
        raise FileNotFoundError(path)

    checked = []
    failures = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            failures.append({
                "line": line_number,
                "status": "invalid_audit_json",
                "detail": str(exc),
            })
            continue

        output_path = record.get("metadata", {}).get("output_path")
        if not output_path:
            checked.append({
                "line": line_number,
                "label": record.get("label"),
                "status": "no_output_path",
            })
            continue

        result_path = Path(output_path)
        if not result_path.exists():
            failures.append({
                "line": line_number,
                "label": record.get("label"),
                "path": str(result_path),
                "status": "missing",
            })
            continue

        try:
            value = json.loads(result_path.read_text(encoding="utf-8"))
            actual = digest(value)
        except Exception as exc:
            failures.append({
                "line": line_number,
                "label": record.get("label"),
                "path": str(result_path),
                "status": "unreadable",
                "detail": f"{type(exc).__name__}: {exc}",
            })
            continue

        expected = record.get("digest_sha256")
        if actual != expected:
            failures.append({
                "line": line_number,
                "label": record.get("label"),
                "path": str(result_path),
                "status": "digest_mismatch",
                "expected": expected,
                "actual": actual,
            })
        else:
            checked.append({
                "line": line_number,
                "label": record.get("label"),
                "path": str(result_path),
                "status": "ok",
            })

    return {
        "audit_log": str(path),
        "records_checked": len(checked) + len(failures),
        "matching": sum(row["status"] == "ok" for row in checked),
        "failures": failures,
        "passed": not failures,
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", default="runs/verification.jsonl")
    p.add_argument("--report", default="")
    p.add_argument("--verbose", action="store_true")
    return p


def main() -> int:
    args = _parser().parse_args()
    result = scrub(args.log)

    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if args.verbose or not result["passed"]:
        print(
            f"verification scrub: checked={result['records_checked']} "
            f"matching={result['matching']} failures={len(result['failures'])}"
        )
        for failure in result["failures"][:20]:
            print(json.dumps(failure, sort_keys=True))

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
