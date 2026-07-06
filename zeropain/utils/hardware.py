from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any


def cpu_hardware_profile() -> dict[str, Any]:
    flags = _cpu_flags()
    model_name = _cpu_model_name()
    return {
        "backend": "cpu",
        "vendor": _cpu_vendor(),
        "model_name": model_name,
        "architecture": platform.machine() or "unknown",
        "logical_cpus": os.cpu_count() or 0,
        "avx2": "avx2" in flags,
        "avx512": any(flag.startswith("avx512") for flag in flags),
        "amx": any(flag.startswith("amx") for flag in flags),
        "vnni": any("vnni" in flag for flag in flags),
        "flags": sorted(flags),
    }


def cpu_training_target() -> dict[str, Any]:
    profile = cpu_hardware_profile()
    return {
        "target_backend": "cpu",
        "target_profile": "intel_xeon_avx2" if profile["vendor"] == "GenuineIntel" and profile["avx2"] else "cpu_generic",
        "profile": profile,
    }


def _cpu_vendor() -> str:
    return _first_cpuinfo_value("vendor_id") or "unknown"


def _cpu_model_name() -> str:
    return _first_cpuinfo_value("model name") or platform.processor() or "unknown"


def _cpu_flags() -> set[str]:
    raw = _first_cpuinfo_value("flags") or _first_cpuinfo_value("Features") or ""
    return {item.strip().lower() for item in raw.split() if item.strip()}


def _first_cpuinfo_value(key: str) -> str | None:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return None
    prefix = f"{key.lower()}:"
    for line in cpuinfo.read_text(errors="ignore").splitlines():
        normalized = line.lower().replace("\t", "")
        if normalized.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None
