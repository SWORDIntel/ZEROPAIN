from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from zeropain.security.cnsa import verify_signature_envelope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zeropain", description="ZeroPain utility commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="Verify a signed run directory")
    verify_parser.add_argument("run_dir", type=Path)

    export_parser = subparsers.add_parser("export", help="Export a run directory as a zip bundle")
    export_parser.add_argument("run_dir", type=Path)
    export_parser.add_argument("-o", "--output", type=Path)

    args = parser.parse_args(argv)
    if args.command == "verify":
        ok, message = verify_run(args.run_dir)
        print(message)
        return 0 if ok else 1
    if args.command == "export":
        output = export_run(args.run_dir, args.output)
        print(output)
        return 0
    return 2


def verify_run(run_dir: Path) -> tuple[bool, str]:
    signature_path = run_dir / "signature.sha384"
    if not run_dir.exists():
        return False, f"Run directory not found: {run_dir}"
    if not signature_path.exists():
        return False, "Signature file missing"
    try:
        signature = json.loads(signature_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False, "Signature file corrupted"

    scope = signature.get("scope", "legacy_core_files")
    digest = signature.get("digest")
    current = _compute_run_digest(run_dir) if scope == "run_files_v2" else _compute_legacy_digest(run_dir)
    if digest != current:
        return False, f"Signature mismatch for {run_dir}"
    ok, message = verify_signature_envelope(
        stored=signature,
        current_digest=current,
        legacy_digest=lambda: _compute_legacy_digest(run_dir),
    )
    if not ok:
        return ok, message
    return True, f"{message} for {run_dir}"


def export_run(run_dir: Path, output: Path | None = None) -> Path:
    ok, message = verify_run(run_dir)
    if not ok:
        raise SystemExit(message)
    bundle_path = output or run_dir.with_suffix(".zip")
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in run_dir.rglob("*") if p.is_file()):
            archive.write(path, path.relative_to(run_dir.parent))
    return bundle_path


def _compute_run_digest(run_dir: Path) -> str:
    hasher = hashlib.sha384()
    for path in _signed_file_paths(run_dir):
        relative = path.relative_to(run_dir).as_posix().encode("utf-8")
        hasher.update(relative)
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _compute_legacy_digest(run_dir: Path) -> str:
    hasher = hashlib.sha384()
    for path in [
        run_dir / "metadata.json",
        run_dir / "config.json",
        run_dir / "metrics.jsonl",
        run_dir / "audit.jsonl",
    ]:
        if path.exists():
            hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _signed_file_paths(run_dir: Path) -> list[Path]:
    signature_path = run_dir / "signature.sha384"
    ignored_dirs = {(run_dir / "checkpoints").resolve(), (run_dir / "logs").resolve()}
    paths: list[Path] = []
    for path in run_dir.rglob("*"):
        if not path.is_file() or path == signature_path:
            continue
        resolved_parent = path.parent.resolve()
        if any(resolved_parent == ignored or ignored in resolved_parent.parents for ignored in ignored_dirs):
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: item.relative_to(run_dir).as_posix())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
