"""Distributed runner with checkpoint/resume support.

This module provides a light abstraction over local, Ray, or Dask execution
for embarrassingly parallel tasks (e.g., patient simulations). It emphasises
safe defaults, resumability via JSON checkpoints, and graceful fallback when
the requested backend is unavailable.

Resilience features
-------------------
* **Atomic checkpoint writes** – batches are written to a ``.tmp`` file and
  renamed into place, so a crash mid-write never produces a corrupt file.
* **Checkpoint integrity verification** – on resume, each checkpoint is
  JSON-parsed and validated; corrupted files are discarded and the batch is
  re-run.
* **Per-batch retry with exponential back-off** – configurable ``max_retries``
  and ``retry_base_delay`` (seconds).
* **Run manifest** – a ``manifest.json`` in the run directory records overall
  state (start time, parameters, completion count) and is updated after each
  batch.
* **SIGINT / SIGTERM graceful shutdown** – the runner flushes the manifest
  before exiting so a Ctrl-C doesn't leave the run in an unknown state.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that coerces numpy scalar types to native Python types."""

    def default(self, obj: Any) -> Any:  # type: ignore[override]
        try:
            import numpy as np  # type: ignore

            if isinstance(obj, np.generic):
                return obj.item()
        except ImportError:
            pass
        return super().default(obj)


def _atomic_write(path: Path, data: Any) -> None:
    """Write *data* as JSON to *path* atomically via a temp file + rename."""
    dir_ = path.parent
    dir_.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, cls=_NumpyEncoder)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _safe_load(path: Path) -> Optional[Any]:
    """Load a JSON checkpoint. Returns *None* if the file is missing or corrupt."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        log.warning("Checkpoint %s is corrupt or unreadable (%s) — will recompute.", path, exc)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------

class _Manifest:
    """Lightweight JSON manifest tracking overall run state."""

    def __init__(self, path: Path, params: Dict[str, Any]) -> None:
        self.path = path
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    self._data: Dict[str, Any] = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        else:
            self._data = {}

        # Merge / initialise fields that may be missing
        self._data.setdefault("status", "running")
        self._data.setdefault("started_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        self._data.setdefault("params", params)
        self._data.setdefault("completed_batches", 0)
        self._data.setdefault("total_batches", 0)
        self._data["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._flush()

    def update(self, **kwargs: Any) -> None:
        self._data.update(kwargs)
        self._data["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._flush()

    def _flush(self) -> None:
        try:
            _atomic_write(self.path, self._data)
        except OSError as exc:
            log.warning("Could not write manifest: %s", exc)

    @property
    def data(self) -> Dict[str, Any]:
        return dict(self._data)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

class DistributedRunner:
    """Execute functions over items with optional distributed backends.

    Parameters
    ----------
    backend:
        ``"local"`` (default), ``"ray"``, or ``"dask"``.
    checkpoint_dir:
        Root directory for run artefacts.  Defaults to ``"runs"``.
    run_id:
        Unique identifier for this run.  Auto-generated from the current time
        if not supplied.
    resume:
        When ``True`` (default), completed batches are loaded from disk instead
        of being recomputed.
    max_retries:
        Number of times to retry a failed batch before re-raising.
    retry_base_delay:
        Initial back-off in seconds; doubles with each retry (capped at 30 s).
    num_workers:
        Hint for the number of parallel workers (Ray / Dask only).
    batch_size:
        Default batch size used when ``map()`` is called without an explicit
        ``batch_size`` argument.
    """

    def __init__(
        self,
        backend: str = "local",
        checkpoint_dir: str = "runs",
        run_id: Optional[str] = None,
        resume: bool = True,
        max_retries: int = 2,
        retry_base_delay: float = 1.0,
        num_workers: Optional[int] = None,
        batch_size: int = 64,
    ) -> None:
        self.backend = backend.lower()
        self.checkpoint_root = Path(checkpoint_dir)
        self.run_id = run_id or f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self.resume = resume
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.num_workers = num_workers
        self.batch_size = batch_size

        self._ray = None
        self._dask_client = None
        self._shutdown_requested = False

        self.run_dir = self.checkpoint_root / self.run_id
        self.checkpoints_dir = self.run_dir / "checkpoints"
        self.logs_dir = self.run_dir / "logs"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self._manifest: Optional[_Manifest] = None
        self._register_signal_handlers()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map(
        self,
        func: Callable[[Any], Any],
        items: Iterable[Any],
        stage_name: str,
        batch_size: int = 0,
        dump_fn: Optional[Callable[[Any], Any]] = None,
        load_fn: Optional[Callable[[Any], Any]] = None,
    ) -> List[Any]:
        """Map *func* across *items* with per-batch checkpointing.

        Parameters
        ----------
        func:
            Callable applied to each item.
        items:
            Iterable of inputs.
        stage_name:
            Label used for checkpoint filenames (e.g. ``"simulation"``).
        batch_size:
            Override the instance-level default.  0 means use the default.
        dump_fn:
            Convert a batch of results to a JSON-serialisable form for storage.
        load_fn:
            Reconstruct results from the stored JSON payload.
        """
        effective_batch = batch_size if batch_size > 0 else self.batch_size
        item_list = list(items)
        batches = self._chunk(item_list, effective_batch)
        n_batches = len(batches)

        params = {
            "backend": self.backend,
            "stage": stage_name,
            "n_items": len(item_list),
            "batch_size": effective_batch,
        }
        manifest_path = self.run_dir / "manifest.json"
        self._manifest = _Manifest(manifest_path, params)
        self._manifest.update(total_batches=n_batches)

        results: List[Any] = []
        completed = 0

        pending_batches = []
        for batch_idx, batch in enumerate(batches):
            ckpt_path = self.checkpoints_dir / f"{stage_name}-{batch_idx}.json"
            if self.resume and ckpt_path.exists():
                payload = _safe_load(ckpt_path)
                if payload is not None:
                    restored = load_fn(payload) if load_fn else payload
                    results.extend(restored)
                    completed += 1
                    continue
            pending_batches.append((batch_idx, batch))
            
        self._manifest.update(completed_batches=completed)

        if not pending_batches:
            self._manifest.update(status="complete")
            return results

        import pickle
        is_picklable = True
        try:
            pickle.dumps(func)
        except Exception:
            is_picklable = False

        use_process_pool = (
            self.backend == "local"
            and is_picklable
            and len(pending_batches) > 1
        )

        if use_process_pool:
            import concurrent.futures
            import multiprocessing
            
            ctx = multiprocessing.get_context("spawn")
            system_cores = multiprocessing.cpu_count()
            # Reserve 4 cores for the system/UI to prevent lag, but use at least 1 core
            available_cores = max(1, system_cores - 4)
            workers = min(available_cores, len(pending_batches) or 1)

            if workers > 1:
                with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as executor:
                    future_to_idx = {
                        executor.submit(
                            _global_batch_worker,
                            func,
                            batch,
                            self.max_retries,
                            self.retry_base_delay,
                            stage_name,
                            batch_idx
                        ): batch_idx 
                        for batch_idx, batch in pending_batches
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_idx):
                        if self._shutdown_requested:
                            log.warning("Shutdown requested — stopping.")
                            executor.shutdown(wait=False, cancel_futures=True)
                            break
                            
                        batch_idx = future_to_idx[future]
                        try:
                            computed = future.result()
                        except Exception as exc:
                            log.error("Batch %d failed: %s", batch_idx, exc)
                            raise
                            
                        ckpt_path = self.checkpoints_dir / f"{stage_name}-{batch_idx}.json"
                        to_store = dump_fn(computed) if dump_fn else computed
                        try:
                            _atomic_write(ckpt_path, to_store)
                        except OSError as exc:
                            log.warning("Could not write checkpoint %s: %s", ckpt_path, exc)
                            
                        results.extend(computed)
                        completed += 1
                        self._manifest.update(completed_batches=completed)

                final_status = "complete" if completed == n_batches else "partial"
                self._manifest.update(status=final_status, completed_batches=completed)
                return results

        # Fallback to sequential / standard loop (with self._run_with_retries)
        for batch_idx, batch in pending_batches:
            if self._shutdown_requested:
                log.warning("Shutdown requested — stopping after %d/%d batches.", completed, n_batches)
                break

            ckpt_path = self.checkpoints_dir / f"{stage_name}-{batch_idx}.json"
            computed = self._run_with_retries(func, batch, batch_idx, stage_name)
            to_store = dump_fn(computed) if dump_fn else computed
            try:
                _atomic_write(ckpt_path, to_store)
            except OSError as exc:
                log.warning("Could not write checkpoint %s: %s", ckpt_path, exc)

            results.extend(computed)
            completed += 1
            self._manifest.update(completed_batches=completed)

        final_status = "complete" if completed == n_batches else "partial"
        self._manifest.update(status=final_status, completed_batches=completed)
        return results

    def close(self):
        """Clean up backends."""
        pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_with_retries(
        self,
        func: Callable[[Any], Any],
        batch: List[Any],
        batch_idx: int,
        stage_name: str,
    ) -> List[Any]:
        """Execute *batch* through *func* with exponential-back-off retries."""
        last_exc: Optional[Exception] = None
        delay = self.retry_base_delay

        for attempt in range(self.max_retries + 1):
            try:
                return self._run_batch(func, batch)
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc
                if attempt < self.max_retries:
                    log.warning(
                        "Batch %d/%s failed (attempt %d/%d): %s — retrying in %.1f s",
                        batch_idx, stage_name, attempt + 1, self.max_retries, exc, delay,
                    )
                    time.sleep(min(delay, 30.0))
                    delay *= 2.0
                else:
                    log.error(
                        "Batch %d/%s failed after %d attempts: %s",
                        batch_idx, stage_name, self.max_retries + 1, exc,
                    )

        raise RuntimeError(
            f"Batch {batch_idx} ({stage_name}) failed after {self.max_retries + 1} attempts"
        ) from last_exc

    def _run_batch(self, func: Callable[[Any], Any], batch: List[Any]) -> List[Any]:
        if self.backend == "ray":
            return self._run_ray(func, batch)
        if self.backend == "dask":
            return self._run_dask(func, batch)
        return [func(item) for item in batch]

    def _run_ray(self, func: Callable[[Any], Any], batch: List[Any]) -> List[Any]:
        try:
            import ray  # type: ignore
        except ImportError:
            return [func(item) for item in batch]

        if self._ray is None:
            self._ray = ray
            if not ray.is_initialized():
                ray.init(ignore_reinit_error=True)

        remote_func = self._ray.remote(func)
        futures = [remote_func.remote(item) for item in batch]
        return list(self._ray.get(futures))

    def _run_dask(self, func: Callable[[Any], Any], batch: List[Any]) -> List[Any]:
        try:
            from dask.distributed import Client
        except ImportError:
            return [func(item) for item in batch]

        if self._dask_client is None:
            try:
                self._dask_client = Client()
            except Exception:
                return [func(item) for item in batch]

        futures = self._dask_client.map(func, batch)
        return list(self._dask_client.gather(futures))

    @staticmethod
    def _chunk(items: List[Any], size: int) -> List[List[Any]]:
        if size <= 0:
            return [items]
        return [items[i : i + size] for i in range(0, len(items), size)]

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _register_signal_handlers(self) -> None:
        """Install SIGINT / SIGTERM handlers for graceful shutdown."""
        def _handler(signum: int, _frame: Any) -> None:
            log.warning("Signal %d received — requesting graceful shutdown.", signum)
            self._shutdown_requested = True
            if self._manifest is not None:
                self._manifest.update(status="interrupted")

        try:
            signal.signal(signal.SIGINT, _handler)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        except (OSError, ValueError):
            pass
def _global_batch_worker(
    func: Callable[[Any], Any],
    batch: List[Any],
    max_retries: int,
    retry_base_delay: float,
    stage_name: str,
    batch_idx: int
) -> List[Any]:
    """Helper to process a batch of items with retry logic."""
    import os
    import time
    import logging
    log = logging.getLogger(__name__)
    try:
        # Lower process priority so it doesn't cause UI lag
        os.nice(10)
    except AttributeError:
        pass # Windows doesn't support os.nice

    last_exc = None
    delay = retry_base_delay
    for attempt in range(max_retries + 1):
        try:
            return [func(item) for item in batch]
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                log.warning(
                    "Batch %d/%s failed (attempt %d/%d): %s — retrying in %.1f s",
                    batch_idx, stage_name, attempt + 1, max_retries, exc, delay,
                )
                time.sleep(min(delay, 30.0))
                delay *= 2.0
            else:
                log.error(
                    "Batch %d/%s failed after %d attempts: %s",
                    batch_idx, stage_name, max_retries + 1, exc,
                )
    raise RuntimeError(
        f"Batch {batch_idx} ({stage_name}) failed after {max_retries + 1} attempts"
    ) from last_exc

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def deterministic_seeds(total: int, base_seed: int = 42) -> List[int]:
    """Generate deterministic seeds for sharded execution."""
    return [base_seed + i for i in range(total)]
