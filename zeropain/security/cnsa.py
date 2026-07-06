"""CNSA 2.0 signature envelope helpers.

The local runtime can always produce a CNSA 2.0-oriented SHA-384 digest envelope.
Full CNSA 2.0 digital-signature compliance requires an external validated signer
for the target post-quantum signature algorithm.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any, Callable, Dict, Optional, Tuple

CNSA_PROFILE = "CNSA_2_0"
CNSA_DIGEST_ALGORITHM = "SHA-384"
CNSA_SIGNATURE_ALGORITHM = "ML-DSA-87"


def build_signature_envelope(
    *,
    digest: str,
    run_id: str,
    signed_utc: str,
    signed_by: str,
    scope: str,
) -> Dict[str, Any]:
    """Build a run signature envelope with CNSA 2.0 metadata."""

    envelope: Dict[str, Any] = {
        "digest": digest,
        "algorithm": "sha384",
        "digest_algorithm": CNSA_DIGEST_ALGORITHM,
        "profile": CNSA_PROFILE,
        "signature_algorithm": CNSA_SIGNATURE_ALGORITHM,
        "scope": scope,
        "run_id": run_id,
        "signed_utc": signed_utc,
        "signed_by": signed_by,
        "signature_mode": "digest_envelope",
        "signature_status": "digest_only_compatibility",
        "cnsa_2_compliant": False,
        "signer": _signer_status(),
    }

    signed = _run_external_signer(envelope)
    if signed:
        envelope.update(signed)
        envelope["signature_mode"] = "detached_signature"
        envelope["signature_status"] = "signed"
        envelope["cnsa_2_compliant"] = True
    return envelope


def verify_signature_envelope(
    *,
    stored: Dict[str, Any],
    current_digest: str,
    legacy_digest: Optional[Callable[[], str]] = None,
) -> Tuple[bool, str]:
    """Verify digest integrity and, when configured, an external CNSA signature."""

    digest = stored.get("digest")
    signed_by = stored.get("signed_by", "unknown")
    scope = stored.get("scope", "legacy_core_files")

    if digest != current_digest:
        if scope == "legacy_core_files" and legacy_digest and digest == legacy_digest():
            return True, f"Signature valid with legacy scope (signed by {signed_by})"
        return False, f"Signature mismatch (signed by {signed_by})"

    profile = stored.get("profile")
    if profile != CNSA_PROFILE:
        return True, f"Signature valid (signed by {signed_by})"

    if stored.get("signature_mode") == "detached_signature":
        verified, detail = _run_external_verifier(stored)
        if verified:
            return True, f"CNSA 2.0 signature valid (signed by {signed_by})"
        return False, f"CNSA 2.0 signature verification failed: {detail}"

    return True, (
        f"CNSA 2.0 digest envelope valid (signed by {signed_by}); "
        "external ML-DSA signer not configured"
    )


def _signer_status() -> Dict[str, Any]:
    return {
        "provider": "external_command" if os.getenv("ZEROPAIN_CNSA_SIGNER_CMD") else "not_configured",
        "sign_command_configured": bool(os.getenv("ZEROPAIN_CNSA_SIGNER_CMD")),
        "verify_command_configured": bool(os.getenv("ZEROPAIN_CNSA_VERIFY_CMD")),
        "required": _env_bool("ZEROPAIN_CNSA_REQUIRE_SIGNATURE"),
    }


def _run_external_signer(envelope: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    command = os.getenv("ZEROPAIN_CNSA_SIGNER_CMD")
    if not command:
        return None
    result = _run_json_command(command, envelope)
    if result is None:
        if _env_bool("ZEROPAIN_CNSA_REQUIRE_SIGNATURE"):
            raise RuntimeError("CNSA signer command failed or returned invalid JSON")
        return {
            "signature_status": "signer_failed",
            "cnsa_2_compliant": False,
        }
    return result


def _run_external_verifier(envelope: Dict[str, Any]) -> Tuple[bool, str]:
    command = os.getenv("ZEROPAIN_CNSA_VERIFY_CMD")
    if not command:
        return False, "external verifier command not configured"
    result = _run_json_command(command, envelope, check=False)
    if not result:
        return False, "verifier failed or returned invalid JSON"
    return bool(result.get("valid")), str(result.get("message", "verifier returned false"))


def _run_json_command(command: str, payload: Dict[str, Any], check: bool = True) -> Optional[Dict[str, Any]]:
    try:
        completed = subprocess.run(
            shlex.split(command),
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=check,
            timeout=30,
        )
        output = completed.stdout.strip()
        if not output:
            return None
        parsed = json.loads(output)
        return parsed if isinstance(parsed, dict) else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}
