"""Tests for DistributedRunner checkpoint resilience features."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.distributed_runner import DistributedRunner, _atomic_write, _safe_load, _Manifest


# ---------------------------------------------------------------------------
# _atomic_write / _safe_load
# ---------------------------------------------------------------------------

def test_atomic_write_creates_file(tmp_path):
    target = tmp_path / "out.json"
    _atomic_write(target, {"ok": True, "value": 42})
    assert target.exists()
    data = json.loads(target.read_text())
    assert data == {"ok": True, "value": 42}


def test_atomic_write_no_tmp_left_on_success(tmp_path):
    target = tmp_path / "out.json"
    _atomic_write(target, [1, 2, 3])
    tmps = list(tmp_path.glob("*.tmp"))
    assert tmps == [], "No .tmp files should remain after successful write"


def test_safe_load_returns_none_for_corrupt(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json!!!}", encoding="utf-8")
    result = _safe_load(bad)
    assert result is None
    assert not bad.exists(), "Corrupt checkpoint should be deleted"


def test_safe_load_returns_none_for_missing(tmp_path):
    result = _safe_load(tmp_path / "nonexistent.json")
    assert result is None


def test_safe_load_roundtrip(tmp_path):
    target = tmp_path / "data.json"
    _atomic_write(target, {"x": [1, 2, 3], "y": 0.5})
    loaded = _safe_load(target)
    assert loaded == {"x": [1, 2, 3], "y": 0.5}


# ---------------------------------------------------------------------------
# _Manifest
# ---------------------------------------------------------------------------

def test_manifest_created(tmp_path):
    m = _Manifest(tmp_path / "manifest.json", {"stage": "test"})
    assert (tmp_path / "manifest.json").exists()
    data = m.data
    assert data["status"] == "running"
    assert "started_at" in data


def test_manifest_persists_on_update(tmp_path):
    path = tmp_path / "manifest.json"
    m = _Manifest(path, {})
    m.update(status="complete", completed_batches=5)
    # Reload from disk
    data = json.loads(path.read_text())
    assert data["status"] == "complete"
    assert data["completed_batches"] == 5


def test_manifest_survives_restart(tmp_path):
    path = tmp_path / "manifest.json"
    m1 = _Manifest(path, {"stage": "sim"})
    m1.update(completed_batches=3, total_batches=10)
    # Second instantiation (simulates restart)
    m2 = _Manifest(path, {"stage": "sim"})
    assert m2.data["completed_batches"] == 3
    assert m2.data["total_batches"] == 10


# ---------------------------------------------------------------------------
# DistributedRunner.map — basic behaviour
# ---------------------------------------------------------------------------

def _make_runner(tmp_path, **kwargs) -> DistributedRunner:
    return DistributedRunner(
        backend="local",
        checkpoint_dir=str(tmp_path),
        run_id="test-run",
        **kwargs,
    )


def test_map_basic(tmp_path):
    runner = _make_runner(tmp_path)
    results = runner.map(lambda x: x * 2, range(10), stage_name="double", batch_size=4)
    assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]


def test_map_writes_checkpoints(tmp_path):
    runner = _make_runner(tmp_path, batch_size=3)
    runner.map(lambda x: x + 1, range(9), stage_name="inc", batch_size=3)
    ckpts = sorted((tmp_path / "test-run" / "checkpoints").glob("inc-*.json"))
    assert len(ckpts) == 3  # 9 items / batch_size 3


def test_map_resumes_from_checkpoints(tmp_path):
    call_count = {"n": 0}

    def counted(x):
        call_count["n"] += 1
        return x * 3

    runner = _make_runner(tmp_path, batch_size=5)
    runner.map(counted, range(10), stage_name="triple")
    first_calls = call_count["n"]

    # Reset counter, resume
    call_count["n"] = 0
    runner2 = _make_runner(tmp_path, batch_size=5, resume=True)
    results = runner2.map(counted, range(10), stage_name="triple")

    assert results == [0, 3, 6, 9, 12, 15, 18, 21, 24, 27]
    assert call_count["n"] == 0, "No items should be recomputed on full resume"


def test_map_recomputes_corrupt_checkpoint(tmp_path):
    runner = _make_runner(tmp_path, batch_size=5)
    runner.map(lambda x: x, range(10), stage_name="copy")

    # Corrupt one checkpoint
    ckpt = tmp_path / "test-run" / "checkpoints" / "copy-0.json"
    ckpt.write_text("{{CORRUPT}}", encoding="utf-8")

    call_count = {"n": 0}
    def counted(x):
        call_count["n"] += 1
        return x

    runner2 = _make_runner(tmp_path, batch_size=5, resume=True)
    results = runner2.map(counted, range(10), stage_name="copy")

    assert sorted(results) == list(range(10))
    assert call_count["n"] == 5, "Only the corrupt batch (5 items) should be recomputed"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

def test_retry_succeeds_on_second_attempt(tmp_path):
    attempt = {"n": 0}

    def flaky(x):
        attempt["n"] += 1
        if attempt["n"] <= 1:
            raise RuntimeError("transient error")
        return x

    runner = _make_runner(tmp_path, max_retries=2, retry_base_delay=0.0, batch_size=10)
    results = runner.map(flaky, [42], stage_name="flaky")
    assert results == [42]


def test_retry_exhausted_raises(tmp_path):
    def always_fails(x):
        raise ValueError("permanent failure")

    runner = _make_runner(tmp_path, max_retries=1, retry_base_delay=0.0, batch_size=10)
    with pytest.raises(RuntimeError, match="failed after"):
        runner.map(always_fails, [1], stage_name="fail")


# ---------------------------------------------------------------------------
# Manifest written by map
# ---------------------------------------------------------------------------

def test_manifest_complete_after_map(tmp_path):
    runner = _make_runner(tmp_path, batch_size=5)
    runner.map(lambda x: x, range(10), stage_name="m")
    manifest = json.loads((tmp_path / "test-run" / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["completed_batches"] == manifest["total_batches"]


# ---------------------------------------------------------------------------
# Numpy type safety
# ---------------------------------------------------------------------------

def test_numpy_scalars_serialise(tmp_path):
    np = pytest.importorskip("numpy")
    runner = _make_runner(tmp_path, batch_size=10)

    def make_numpy(_):
        return {"val": np.float64(3.14), "flag": np.bool_(True), "count": np.int32(7)}

    results = runner.map(make_numpy, [0], stage_name="numpy",
                         dump_fn=lambda b: [r for r in b],
                         load_fn=lambda p: p)
    ckpt = tmp_path / "test-run" / "checkpoints" / "numpy-0.json"
    data = json.loads(ckpt.read_text())
    # Values should be native Python types in the checkpoint
    assert isinstance(data[0]["val"], float)
    assert isinstance(data[0]["flag"], bool)
    assert isinstance(data[0]["count"], int)
