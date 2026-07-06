import pytest

from zeropain.database.backends import database_backend_status, require_database_backend


def test_sqlmodel_backend_is_default(monkeypatch):
    monkeypatch.delenv("ZEROPAIN_DB_BACKEND", raising=False)
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)

    status = database_backend_status()

    assert status.backend == "sqlmodel"
    assert status.active == "sqlmodel"
    assert status.available is True
    assert status.qihse_repo == "https://github.com/SWORDIntel/QIHSE"
    assert status.keystone_repo == "https://github.com/SWORDIntel/KEYSTONE"


def test_qihse_backend_requires_native_bindings(monkeypatch):
    monkeypatch.setenv("ZEROPAIN_DB_BACKEND", "qihse")
    monkeypatch.delenv("QIHSE_HOME", raising=False)
    monkeypatch.delenv("KEYSTONE_HOME", raising=False)

    status = database_backend_status()

    if status.available:
        assert require_database_backend().active == "qihse"
    else:
        with pytest.raises(RuntimeError, match="QIHSE backend selected"):
            require_database_backend()
