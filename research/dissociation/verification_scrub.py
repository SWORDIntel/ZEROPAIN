"""Backward-compatible research entrypoint for the project-wide scrubber."""

from zeropain.verification_scrub import main, scrub

__all__ = ["main", "scrub"]

if __name__ == "__main__":
    raise SystemExit(main())
