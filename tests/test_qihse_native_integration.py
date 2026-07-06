from pathlib import Path

import pytest

from zeropain.database.backends import database_backend_status
from zeropain.database.qihse_backend import mirror_database_record


def test_bundled_qihse_keystone_status_when_built(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    qihse_home = root / "third_party" / "QIHSE"
    keystone_home = root / "third_party" / "KEYSTONE"
    if not (qihse_home / "libqihse.so").exists():
        pytest.skip("bundled QIHSE native library is not built")

    monkeypatch.setenv("ZEROPAIN_DB_BACKEND", "qihse")
    monkeypatch.setenv("QIHSE_HOME", str(qihse_home))
    monkeypatch.setenv("KEYSTONE_HOME", str(keystone_home))

    status = database_backend_status()

    assert status.active == "qihse"
    assert status.available is True
    assert status.keystone_bridge is True


def test_bundled_qihse_record_mirror_when_built(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    qihse_home = root / "third_party" / "QIHSE"
    keystone_home = root / "third_party" / "KEYSTONE"
    if not (qihse_home / "libqihse.so").exists():
        pytest.skip("bundled QIHSE native library is not built")

    monkeypatch.setenv("ZEROPAIN_DB_BACKEND", "qihse")
    monkeypatch.setenv("QIHSE_HOME", str(qihse_home))
    monkeypatch.setenv("KEYSTONE_HOME", str(keystone_home))
    monkeypatch.setenv("QIHSE_DB_PATH", str(tmp_path / "records.qkv"))

    assert mirror_database_record("tests", "native", {"ok": True}) is True
    assert (tmp_path / "records.qkv").exists()
