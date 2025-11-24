"""Lightweight dependency bootstrapper for ZeroPain."""

from __future__ import annotations

import importlib
import subprocess
import sys
from typing import Iterable, Optional


def ensure_dependencies(packages: Iterable[str], console: Optional[object] = None) -> None:
    """Ensure required packages are installed.

    Attempts to import each package; if missing, installs via pip using the
    current interpreter. Errors are swallowed with a console-friendly message
    so the application can fall back gracefully when offline.
    """

    for pkg in packages:
        try:
            importlib.import_module(pkg)
            continue
        except ImportError:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pkg],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                importlib.import_module(pkg)
            except Exception as exc:  # pragma: no cover - best-effort bootstrap
                if console is not None:
                    try:
                        console.print(
                            f"[yellow]Dependency '{pkg}' missing; pip install failed ({exc})."
                        )
                    except Exception:
                        pass
                else:
                    sys.stderr.write(
                        f"Dependency '{pkg}' missing; pip install failed ({exc}).\n"
                    )


__all__ = ["ensure_dependencies"]
