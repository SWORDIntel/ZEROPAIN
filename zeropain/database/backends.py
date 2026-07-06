"""Database backend selection and QIHSE/KEYSTONE readiness checks."""

from __future__ import annotations

import ctypes.util
import importlib.util
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict

QIHSE_REPO_URL = "https://github.com/SWORDIntel/QIHSE"
KEYSTONE_REPO_URL = "https://github.com/SWORDIntel/KEYSTONE"
REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_QIHSE_HOME = REPO_ROOT / "third_party" / "QIHSE"
BUNDLED_KEYSTONE_HOME = REPO_ROOT / "third_party" / "KEYSTONE"


@dataclass(frozen=True)
class DatabaseBackendStatus:
    backend: str
    active: str
    available: bool
    qihse_python: bool
    qihse_library: bool
    keystone_bridge: bool
    qihse_repo: str
    keystone_repo: str
    qihse_home: str | None = None
    keystone_home: str | None = None
    message: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def database_backend_status() -> DatabaseBackendStatus:
    backend = _configured_backend()
    qihse_home = _configured_home("QIHSE_HOME", BUNDLED_QIHSE_HOME)
    keystone_home = _configured_home("KEYSTONE_HOME", BUNDLED_KEYSTONE_HOME)
    qihse_python = importlib.util.find_spec("qihse") is not None or _has_bundled_python(qihse_home)
    qihse_library = bool(ctypes.util.find_library("qihse")) or _has_library(qihse_home, "libqihse.so")
    keystone_bridge = _has_keystone_bridge(qihse_home, keystone_home)
    qihse_available = qihse_python and qihse_library

    if backend == "qihse":
        active = "qihse" if qihse_available else "unavailable"
        available = qihse_available
        message = (
            "QIHSE backend ready"
            if qihse_available
            else "QIHSE backend selected but qihse Python bindings or libqihse are not available"
        )
    else:
        active = "sqlmodel"
        available = True
        message = "SQLModel backend active"

    return DatabaseBackendStatus(
        backend=backend,
        active=active,
        available=available,
        qihse_python=qihse_python,
        qihse_library=qihse_library,
        keystone_bridge=keystone_bridge,
        qihse_repo=QIHSE_REPO_URL,
        keystone_repo=KEYSTONE_REPO_URL,
        qihse_home=str(qihse_home) if qihse_home else None,
        keystone_home=str(keystone_home) if keystone_home else None,
        message=message,
    )


def require_database_backend() -> DatabaseBackendStatus:
    status = database_backend_status()
    if status.backend == "qihse" and not status.available:
        raise RuntimeError(status.message)
    return status


def _configured_backend() -> str:
    value = os.getenv("ZEROPAIN_DB_BACKEND") or os.getenv("DATABASE_BACKEND", "sqlmodel")
    return value.strip().lower()


def _has_library(home: str | None, filename: str) -> bool:
    if not home:
        return False
    root = Path(home)
    return any((root / rel / filename).exists() for rel in ("", "lib", "build", "build/lib"))


def _has_keystone_bridge(qihse_home: Path | str | None, keystone_home: Path | str | None) -> bool:
    candidates: list[Path] = []
    if qihse_home:
        candidates.append(Path(qihse_home) / "include" / "qihse_keystone_bridge.h")
    if keystone_home:
        candidates.extend(
            [
                Path(keystone_home) / "include" / "qihse_keystone_bridge.h",
                Path(keystone_home) / "src" / "qihse_keystone_bridge.c",
            ]
        )
    return any(path.exists() for path in candidates)


def _configured_home(env_name: str, bundled: Path) -> Path | None:
    value = os.getenv(env_name)
    if value:
        return Path(value)
    return bundled if bundled.exists() else None


def _has_bundled_python(home: Path | str | None) -> bool:
    if not home:
        return False
    return (Path(home) / "python" / "qihse" / "__init__.py").exists()
