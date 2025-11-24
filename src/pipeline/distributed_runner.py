"""Distributed runner with checkpoint/resume support.

This module provides a light abstraction over local, Ray, or Dask execution
for embarrassingly parallel tasks (e.g., patient simulations). It emphasizes
safe defaults, resumability via JSON checkpoints, and graceful fallback when
the requested backend is unavailable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional


class DistributedRunner:
    """Execute functions over items with optional distributed backends."""

    def __init__(
        self,
        backend: str = "local",
        checkpoint_dir: str = "runs",
        run_id: Optional[str] = None,
        resume: bool = True,
        max_retries: int = 1,
        num_workers: Optional[int] = None,
    ):
        self.backend = backend.lower()
        self.checkpoint_root = Path(checkpoint_dir)
        self.run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
        self.resume = resume
        self.max_retries = max_retries
        self.num_workers = num_workers

        self._ray = None
        self._dask_client = None

        self.run_dir = self.checkpoint_root / self.run_id
        self.checkpoints_dir = self.run_dir / "checkpoints"
        self.logs_dir = self.run_dir / "logs"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def map(
        self,
        func: Callable[[Any], Any],
        items: Iterable[Any],
        stage_name: str,
        batch_size: int = 64,
        dump_fn: Optional[Callable[[Any], Any]] = None,
        load_fn: Optional[Callable[[Any], Any]] = None,
    ) -> List[Any]:
        """Map function across items with checkpointed batches."""

        batches = self._chunk(list(items), batch_size)
        results: List[Any] = []

        for batch_idx, batch in enumerate(batches):
            ckpt_path = self.checkpoints_dir / f"{stage_name}-{batch_idx}.json"

            if self.resume and ckpt_path.exists():
                with ckpt_path.open("r", encoding="utf-8") as f:
                    payload = json.load(f)
                restored = load_fn(payload) if load_fn else payload
                results.extend(restored)
                continue

            computed = self._run_batch(func, batch)
            to_store = dump_fn(computed) if dump_fn else computed

            with ckpt_path.open("w", encoding="utf-8") as f:
                json.dump(to_store, f, indent=2)

            results.extend(computed)

        return results

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
                self._dask_client = Client()  # local client
            except Exception:
                return [func(item) for item in batch]

        futures = self._dask_client.map(func, batch)
        return list(self._dask_client.gather(futures))

    @staticmethod
    def _chunk(items: List[Any], size: int) -> List[List[Any]]:
        if size <= 0:
            return [items]
        return [items[i : i + size] for i in range(0, len(items), size)]


def deterministic_seeds(total: int, base_seed: int = 42) -> List[int]:
    """Generate deterministic seeds for sharded execution."""
    return [base_seed + i for i in range(total)]
