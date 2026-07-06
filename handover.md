
• Verification passed so far. I’m doing one last metadata sanity check because I added a direct optional dependency for QIHSE in pyproject.toml.

• Ran ZEROPAIN_DB_BACKEND=qihse python - <<'PY'
  │ from zeropain.database.backends import database_backend_status
  │ print(database_backend_status().as_dict())
  │ … +1 lines
  └ {'backend': 'qihse', 'active': 'qihse', 'available': True, 'qihse_python': True, 'qihse_library': True, 'keystone_bridge': False, 'qihse_repo':
    'https://github.com/SWORDIntel/QIHSE', 'keystone_repo': 'https://github.com/SWORDIntel/KEYSTONE', 'qihse_home': None, 'keystone_home': None,
    'message': 'QIHSE backend ready'}

• Ran python - <<'PY'
  │ from zeropain.database.backends import database_backend_status
  │ print(database_backend_status().as_dict())
  │ … +1 lines
  └ {'backend': 'sqlmodel', 'active': 'sqlmodel', 'available': True, 'qihse_python': True, 'qihse_library': True, 'keystone_bridge': False,
    'qihse_repo': 'https://github.com/SWORDIntel/QIHSE', 'keystone_repo': 'https://github.com/SWORDIntel/KEYSTONE', 'qihse_home': None,
    'keystone_home': None, 'message': 'SQLModel backend active'}

• Ran python -m pip install -e . --dry-run
  └ error: externally-managed-environment

    … +17 lines (ctrl + t to view transcript)
    breaking your Python installation or OS, by passing --break-system-packages.
    hint: See PEP 668 for the detailed specification.

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• The local environment actually detects QIHSE Python bindings and libqihse, but not the KEYSTONE bridge. I’m checking the Python API shape now so the
  backend hook can do a real smoke open when QIHSE is selected.

• Explored
  └ Read __init__.py, kv.py, document.py

• Ran python - <<'PY'
  │ import ctypes.util, importlib.util
  │ print('qihse spec', importlib.util.find_spec('qihse'))
  │ … +2 lines
  └ qihse spec ModuleSpec(name='qihse', loader=<_frozen_importlib_external.SourceFileLoader object at 0x7239dbc7f230>, origin='/usr/local/lib/
    python3.13/dist-packages/qihse/__init__.py', submodule_search_locations=['/usr/local/lib/python3.13/dist-packages/qihse'])
    libqihse libqihse.so

• Ran python - <<'PY'
  │ import qihse, inspect
  │ print(qihse)
  │ … +7 lines
  └ <module 'qihse' from '/usr/local/lib/python3.13/dist-packages/qihse/__init__.py'>
    ['DistanceMetric', 'DocumentStore', 'KVStore', 'TimeSeriesDB', 'UWPServer', 'VectorDB', 'VectorQuery', 'VectorResult', '__all__', '__builtins__',
    … +8 lines (ctrl + t to view transcript)
    VectorQuery <class 'qihse.core.VectorQuery'>
    VectorResult <class 'qihse.core.VectorResult'>

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• QIHSE is installed here and exposes KV/document bindings, so I’m tightening this from “status only” into a backend mirror: when
  ZEROPAIN_DB_BACKEND=qihse, job/run records are written into QIHSE KV/document storage while SQLModel remains the compatibility session layer for
  FastAPI dependencies.

• Edited 3 files (+96 -0)
  └ zeropain/api/main.py (+18 -0)
     18  from .routes import operations as ops_routes
     19 +from zeropain.database.qihse_backend import mirror_database_record
     20  from zeropain.docking import DockingJobSpec, run_docking_job
        ⋮
    127      session.refresh(job_record)
    128 +    _mirror_job_record(job_record)
    129
        ⋮
    182      session.commit()
    183 +    _mirror_job_record(job_record)
    184      return response
        ⋮
    216      out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    217 +
    218 +
    219 +def _mirror_job_record(job_record: Job) -> None:
    220 +    mirror_database_record(
    221 +        "jobs",
    222 +        str(job_record.id),
    223 +        {
    224 +            "id": job_record.id,
    225 +            "job_type": job_record.job_type,
    226 +            "status": job_record.status,
    227 +            "payload": job_record.payload,
    228 +            "created_at": job_record.created_at.isoformat(),
    229 +            "updated_at": job_record.updated_at.isoformat(),
    230 +        },
    231 +    )

  └ zeropain/api/routes/operations.py (+19 -0)
     17  from ..models import Job, utc_now
     18 +from zeropain.database.qihse_backend import mirror_database_record
     19  from utils.experiment_tracking import ExperimentTracker
        ⋮
    304      session.refresh(job_record)
    305 +    _mirror_job_record(job_record)
    306
        ⋮
    346          session.commit()
    347 +        _mirror_job_record(job_record)
    348          return response
        ⋮
    354          session.commit()
    355 +        _mirror_job_record(job_record)
    356          raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}") from exc
        ⋮
    571
    572 +def _mirror_job_record(job_record: Job) -> None:
    573 +    mirror_database_record(
    574 +        "jobs",
    575 +        str(job_record.id),
    576 +        {
    577 +            "id": job_record.id,
    578 +            "job_type": job_record.job_type,
    579 +            "status": job_record.status,
    580 +            "payload": job_record.payload,
    581 +            "created_at": job_record.created_at.isoformat(),
    582 +            "updated_at": job_record.updated_at.isoformat(),
    583 +        },
    584 +    )
    585 +
    586 +
    587  __all__ = [

  └ zeropain/database/qihse_backend.py (+59 -0)
     1 +"""QIHSE persistence bridge for ZeroPain job and run records."""
     2 +
     3 +from __future__ import annotations
     4 +
     5 +import hashlib
     6 +import json
     7 +import os
     8 +from pathlib import Path
     9 +from typing import Any, Dict
    10 +
    11 +from .backends import database_backend_status
    12 +
    13 +
    14 +class QihseRecordStore:
    15 +    """Small JSON record store backed by QIHSE KV and document APIs."""
    16 +
    17 +    def __init__(self, path: str | None = None):
    18 +        import qihse
    19 +
    20 +        self.path = Path(path or os.getenv("QIHSE_DB_PATH", "runs/qihse_backend.kv"))
    21 +        self.path.parent.mkdir(parents=True, exist_ok=True)
    22 +        self._kv = qihse.KVStore()
    23 +        if self.path.exists():
    24 +            self._kv.load(str(self.path))
    25 +        self._doc = qihse.DocumentStore(self._kv)
    26 +
    27 +    def close(self) -> None:
    28 +        self._doc.close()
    29 +        self._kv.close()
    30 +
    31 +    def put_json(self, namespace: str, key: str, payload: Dict[str, Any]) -> None:
    32 +        record_key = f"{namespace}:{key}"
    33 +        encoded = json.dumps(payload, sort_keys=True, default=str)
    34 +        if not self._kv.set(record_key, encoded):
    35 +            raise RuntimeError(f"QIHSE KV write failed for {record_key}")
    36 +        self._doc.insert_json(_document_id(record_key), encoded)
    37 +        self._kv.save(str(self.path))
    38 +
    39 +
    40 +def mirror_database_record(namespace: str, key: str, payload: Dict[str, Any]) -> bool:
    41 +    """Mirror a JSON record into QIHSE when that backend is explicitly selected."""
    42 +
    43 +    status = database_backend_status()
    44 +    if status.backend != "qihse":
    45 +        return False
    46 +    if not status.available:
    47 +        raise RuntimeError(status.message)
    48 +
    49 +    store = QihseRecordStore()
    50 +    try:
    51 +        store.put_json(namespace, key, payload)
    52 +    finally:
    53 +        store.close()
    54 +    return True
    55 +
    56 +
    57 +def _document_id(key: str) -> int:
    58 +    digest = hashlib.sha256(key.encode("utf-8")).digest()
    59 +    return int.from_bytes(digest[:8], byteorder="big", signed=False)

• Ran git diff --check
  └ (no output)

• Ran ZEROPAIN_DB_BACKEND=qihse QIHSE_DB_PATH=/tmp/zeropain-qihse-smoke.kv python - <<'PY'
  │ from zeropain.database.qihse_backend import mirror_database_record
  │ print(mirror_database_record('smoke', 'one', {'ok': True}))
  │ … +1 lines
  └
    [QIHSE QDD] GeoIP databases not found or incomplete.
    … +7 lines (ctrl + t to view transcript)

    True

⚠ Heads up, you have less than 5% of your 5h limit left. Run /status for a breakdown.

• Ran python -m pytest -q
  └ ..........................                                               [100%]
    26 passed in 4.71s

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• The QIHSE smoke write succeeds on this host, with QIHSE reporting missing optional GeoIP data. I’m tightening the failed docking path so QIHSE
  mirrors failed job records as well.

• Edited 2 files (+2 -1)
  └ README.md (+1 -1)
    73  - Default: `ZEROPAIN_DB_BACKEND=sqlmodel` uses the existing SQLModel engine with `DATABASE_URL`.
    74 -- QIHSE: `ZEROPAIN_DB_BACKEND=qihse` requires QIHSE Python bindings plus `libqihse.so`; install with `pip install "zeropain[qihse]"` or build
        from `https://github.com/SWORDIntel/QIHSE`.
    74 +- QIHSE: `ZEROPAIN_DB_BACKEND=qihse` requires QIHSE Python bindings plus `libqihse.so`; install with `pip install "zeropain[qihse]"` or build
        from `https://github.com/SWORDIntel/QIHSE`. In this mode, API job records are mirrored into QIHSE KV/document storage while SQLModel remains t
        he FastAPI compatibility session layer.
    75  - KEYSTONE acceleration is detected through `KEYSTONE_HOME` or `QIHSE_HOME` when `qihse_keystone_bridge.h` or `qihse_keystone_bridge.c` is pre
        sent from `https://github.com/SWORDIntel/KEYSTONE`.

  └ zeropain/api/main.py (+1 -0)
    146          session.commit()
    147 +        _mirror_job_record(job_record)
    148          raise

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• I’m rerunning the full verification set after the last mirror-path patch.

• Ran git diff --check && python -m zeropain.cli.main --help
  └ usage: zeropain [-h] {verify,export} ...

    … +7 lines (ctrl + t to view transcript)
    options:
      -h, --help       show this help message and exit

• Ran npm audit --audit-level=moderate && npm run build
  └ found 0 vulnerabilities

    … +12 lines (ctrl + t to view transcript)

    ✓ built in 835ms

• Ran python -m pytest -q
  └ ..........................                                               [100%]
    26 passed in 5.47s

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Verification is green. I’m collecting the exact file references and status so the final note is concrete.

• Ran pwd
  └ /fast/Main Workspace/ZEROPAIN

• Explored
  └ Read cnsa.py, backends.py, qihse_backend.py, README.md


› build and fully intergrate QIHSE and KEYSTONE


• I’ll move from detection/mirroring to a real local native integration: vendor/build QIHSE and KEYSTONE, wire their build outputs into the app’s
  runtime configuration, and add a smoke test path that exercises QIHSE with the built library.

• Explored
  └ Read Makefile
    Search README.md in zeropain-qihse
    Search README.md in zeropain-keystone

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• The native makefiles are CPU-friendly if we force the host’s actual ISA. This machine is AVX2/FMA only, so I’ll build with AVX2 enabled and AVX-512/
  VNNI/AMX disabled, then wire QIHSE_HOME, KEYSTONE_HOME, LD_LIBRARY_PATH, and the Python binding path through repo scripts and tests.

• Ran mkdir -p third_party && if [ ! -d third_party/KEYSTONE/.git ]; then git clone https://github.com/SWORDIntel/KEYSTONE.git third_party/KEYSTONE;
  │ else git -C third_party/KEYSTONE rev-parse HEAD; fi
  └ (no output)

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• KEYSTONE cloned; QIHSE is still cloning because it is larger. I’ll poll that before starting native builds.

• Ran mkdir -p third_party && if [ ! -d third_party/QIHSE/.git ]; then git clone https://github.com/SWORDIntel/QIHSE.git third_party/QIHSE; else git
  │ -C third_party/QIHSE rev-parse HEAD; fi
Updating files:  52% (594/1163)163)
    … +11 lines (ctrl + t to view transcript)
Updating files: 100% (1163/1163), done.

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Both native repos are now under third_party/. I’m starting with KEYSTONE because its QIHSE bridge build is smaller, then I’ll build QIHSE’s ctypes
  library and adjust paths around whatever the native build emits.

• Ran make clean >/dev/null 2>&1 || true; make lib-ctypes QIHSE_ENABLE_AVX2=1 QIHSE_ENABLE_AVX512=0 QIHSE_ENABLE_AVX_VNNI=0 QIHSE_ENABLE_AMX=0
  └ make: *** No rule to make target 'vendor/tree-sitter/lib/src/lib.c', needed by 'lib-ctypes'.  Stop.

• Ran make clean >/dev/null 2>&1 || true; make KEYSTONE_ENABLE_QIHSE_BRIDGE=1 QIHSE_ROOT=/fast/Main\ Workspace/ZEROPAIN/third_party/QIHSE
  │ KEYSTONE_ENABLE_AVX2=1 KEYSTONE_ENABLE_AVX512=0 KEYSTONE_ENABLE_FORTRAN=0 KEYSTONE_ENABLE_CUDA=0 KEYSTONE_ENABLE_TAR_ZST=0 tests
  └ gcc -O3 -march=native -Wall -Wextra -Werror=implicit-function-declaration -I./include -DKEYSTONE_ENABLE_PLATFORM_TUNING
    -DKEYSTONE_ENABLE_QIHSE_BRIDGE -I"/fast/Main Workspace/ZEROPAIN/third_party/QIHSE/include" -mavx2 -c src/dsmil_keystone_wrapper.c -o src/
    … +50 lines (ctrl + t to view transcript)
    dsmil_micro_model.o tests/test_core_native.o -lm -L"/fast/Main Workspace/ZEROPAIN/third_party/QIHSE" -lqihse -Wl,-rpath,"/fast/Main Workspace/
    ZEROPAIN/third_party/QIHSE"

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• KEYSTONE compiled its bridge-enabled test binaries, but QIHSE stopped because its vendored tree-sitter submodule was not initialized. I’m
  initializing QIHSE submodules and rebuilding QIHSE; then I’ll relink KEYSTONE against the repo-local libqihse.so instead of whatever the system
  linker can find.

• Ran git -C third_party/QIHSE rev-parse HEAD && git -C third_party/KEYSTONE rev-parse HEAD
  └ 4c6a0c4ac5a02d8463c23b646c3c13dde34f7ac0
    173d84c1ca27daefaea062d00e94e399bdc2d4d7

• Ran git submodule update --init --recursive
  └ Submodule 'vendor/tree-sitter' (https://github.com/tree-sitter/tree-sitter.git) registered for path 'vendor/tree-sitter'
    Submodule 'vendor/wasm3' (https://github.com/wasm3/wasm3) registered for path 'vendor/wasm3'
    … +2 lines (ctrl + t to view transcript)
    Submodule path 'vendor/tree-sitter': checked out '9fc2f486a8c1e1f5a4b1954cdcd240fcd09eb003'
    Submodule path 'vendor/wasm3': checked out 'd77cd814aa0bc68cb1df917580a6304d34cfb30b'

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Submodules are initialized. I’m rebuilding QIHSE with the local AVX2-only profile.

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• QIHSE is still compiling. It links a broad native feature set, so I’m waiting for completion before changing app code around the build outputs.

• Waited for background terminal · make lib-ctypes QIHSE_ENABLE_AVX2=1 QIHSE_ENABLE_AVX512=0 QIHSE_ENABLE_AVX_VNNI=0 QIHSE_ENABLE_AMX=0

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• The QIHSE compile is still running without new output. I’ll continue polling; if it fails on optional native libraries, I’ll isolate the supported
  CPU/KV/document subset instead of leaving the integration half-built.

• Ran make lib-ctypes QIHSE_ENABLE_AVX2=1 QIHSE_ENABLE_AVX512=0 QIHSE_ENABLE_AVX_VNNI=0 QIHSE_ENABLE_AMX=0
  └ src/bombe/qihse_hetero.c: In function ‘qihse_benchmark_device_int8’:
    src/bombe/qihse_hetero.c:166:19: warning: unused variable ‘rbuf’ [-Wunused-variable]
      166 |     unsigned char rbuf[8];
          |                   ^~~~
    libqihse.so (ctypes) build successful

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• QIHSE built successfully. I’m now relinking KEYSTONE after the local libqihse.so exists, then I’ll update ZeroPain so it prefers the bundled native
  repos without requiring environment variables.

• Explored
  └ List libqihse.so
    Read .gitignore

• Ran make clean >/dev/null 2>&1 || true; make KEYSTONE_ENABLE_QIHSE_BRIDGE=1 QIHSE_ROOT=/fast/Main\ Workspace/ZEROPAIN/third_party/QIHSE
  │ KEYSTONE_ENABLE_AVX2=1 KEYSTONE_ENABLE_AVX512=0 KEYSTONE_ENABLE_FORTRAN=0 KEYSTONE_ENABLE_CUDA=0 KEYSTONE_ENABLE_TAR_ZST=0 tests
  └ gcc -O3 -march=native -Wall -Wextra -Werror=implicit-function-declaration -I./include -DKEYSTONE_ENABLE_PLATFORM_TUNING
    -DKEYSTONE_ENABLE_QIHSE_BRIDGE -I"/fast/Main Workspace/ZEROPAIN/third_party/QIHSE/include" -mavx2 -c src/dsmil_keystone_wrapper.c -o src/
    … +50 lines (ctrl + t to view transcript)
    dsmil_micro_model.o tests/test_core_native.o -lm -L"/fast/Main Workspace/ZEROPAIN/third_party/QIHSE" -lqihse -Wl,-rpath,"/fast/Main Workspace/
    ZEROPAIN/third_party/QIHSE"

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• The native artifacts exist now. I’m making the app prefer third_party/QIHSE and third_party/KEYSTONE automatically, adding a repeatable build
  script, and keeping those large cloned repos out of normal source diffs.

• Edited 6 files (+128 -6)
  └ .gitignore (+4 -0)
    90  completed_jobs/
    91 +
    92 +# Native backend working trees are cloned by scripts/build_native_backends.sh.
    93 +third_party/QIHSE/
    94 +third_party/KEYSTONE/

  └ README.md (+10 -0)
    77
    78 +Build the local native backends on the Intel AVX2 CPU host:
    79 +
    80 +```bash
    81 +scripts/build_native_backends.sh
    82 +export ZEROPAIN_DB_BACKEND=qihse
    83 +export QIHSE_HOME="$PWD/third_party/QIHSE"
    84 +export KEYSTONE_HOME="$PWD/third_party/KEYSTONE"
    85 +export LD_LIBRARY_PATH="$QIHSE_HOME:${LD_LIBRARY_PATH:-}"
    86 +```
    87 +
    88  ## Population, Medication, and Pharmacology Controls

  └ scripts/build_native_backends.sh (+39 -0)
     1 +#!/usr/bin/env bash
     2 +set -euo pipefail
     3 +
     4 +ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
     5 +THIRD_PARTY_DIR="${ROOT_DIR}/third_party"
     6 +QIHSE_DIR="${THIRD_PARTY_DIR}/QIHSE"
     7 +KEYSTONE_DIR="${THIRD_PARTY_DIR}/KEYSTONE"
     8 +
     9 +mkdir -p "${THIRD_PARTY_DIR}"
    10 +
    11 +if [[ ! -d "${QIHSE_DIR}/.git" ]]; then
    12 +  git clone https://github.com/SWORDIntel/QIHSE.git "${QIHSE_DIR}"
    13 +fi
    14 +
    15 +if [[ ! -d "${KEYSTONE_DIR}/.git" ]]; then
    16 +  git clone https://github.com/SWORDIntel/KEYSTONE.git "${KEYSTONE_DIR}"
    17 +fi
    18 +
    19 +git -C "${QIHSE_DIR}" submodule update --init --recursive
    20 +
    21 +make -C "${QIHSE_DIR}" lib-ctypes \
    22 +  QIHSE_ENABLE_AVX2=1 \
    23 +  QIHSE_ENABLE_AVX512=0 \
    24 +  QIHSE_ENABLE_AVX_VNNI=0 \
    25 +  QIHSE_ENABLE_AMX=0
    26 +
    27 +make -C "${KEYSTONE_DIR}" clean >/dev/null 2>&1 || true
    28 +make -C "${KEYSTONE_DIR}" tests \
    29 +  KEYSTONE_ENABLE_QIHSE_BRIDGE=1 \
    30 +  QIHSE_ROOT="${QIHSE_DIR}" \
    31 +  KEYSTONE_ENABLE_AVX2=1 \
    32 +  KEYSTONE_ENABLE_AVX512=0 \
    33 +  KEYSTONE_ENABLE_FORTRAN=0 \
    34 +  KEYSTONE_ENABLE_CUDA=0 \
    35 +  KEYSTONE_ENABLE_TAR_ZST=0
    36 +
    37 +echo "QIHSE_HOME=${QIHSE_DIR}"
    38 +echo "KEYSTONE_HOME=${KEYSTONE_DIR}"
    39 +echo "LD_LIBRARY_PATH=${QIHSE_DIR}:\${LD_LIBRARY_PATH:-}"

  └ tests/test_qihse_native_integration.py (+40 -0)
     1 +from pathlib import Path
     2 +
     3 +import pytest
     4 +
     5 +from zeropain.database.backends import database_backend_status
     6 +from zeropain.database.qihse_backend import mirror_database_record
     7 +
     8 +
     9 +def test_bundled_qihse_keystone_status_when_built(monkeypatch):
    10 +    root = Path(__file__).resolve().parents[1]
    11 +    qihse_home = root / "third_party" / "QIHSE"
    12 +    keystone_home = root / "third_party" / "KEYSTONE"
    13 +    if not (qihse_home / "libqihse.so").exists():
    14 +        pytest.skip("bundled QIHSE native library is not built")
    15 +
    16 +    monkeypatch.setenv("ZEROPAIN_DB_BACKEND", "qihse")
    17 +    monkeypatch.setenv("QIHSE_HOME", str(qihse_home))
    18 +    monkeypatch.setenv("KEYSTONE_HOME", str(keystone_home))
    19 +
    20 +    status = database_backend_status()
    21 +
    22 +    assert status.active == "qihse"
    23 +    assert status.available is True
    24 +    assert status.keystone_bridge is True
    25 +
    26 +
    27 +def test_bundled_qihse_record_mirror_when_built(monkeypatch, tmp_path):
    28 +    root = Path(__file__).resolve().parents[1]
    29 +    qihse_home = root / "third_party" / "QIHSE"
    30 +    keystone_home = root / "third_party" / "KEYSTONE"
    31 +    if not (qihse_home / "libqihse.so").exists():
    32 +        pytest.skip("bundled QIHSE native library is not built")
    33 +
    34 +    monkeypatch.setenv("ZEROPAIN_DB_BACKEND", "qihse")
    35 +    monkeypatch.setenv("QIHSE_HOME", str(qihse_home))
    36 +    monkeypatch.setenv("KEYSTONE_HOME", str(keystone_home))
    37 +    monkeypatch.setenv("QIHSE_DB_PATH", str(tmp_path / "records.qkv"))
    38 +
    39 +    assert mirror_database_record("tests", "native", {"ok": True}) is True
    40 +    assert (tmp_path / "records.qkv").exists()

  └ zeropain/database/backends.py (+22 -6)
     13  KEYSTONE_REPO_URL = "https://github.com/SWORDIntel/KEYSTONE"
     14 +REPO_ROOT = Path(__file__).resolve().parents[2]
     15 +BUNDLED_QIHSE_HOME = REPO_ROOT / "third_party" / "QIHSE"
     16 +BUNDLED_KEYSTONE_HOME = REPO_ROOT / "third_party" / "KEYSTONE"
     17
        ⋮
     38      backend = _configured_backend()
     36 -    qihse_home = os.getenv("QIHSE_HOME")
     37 -    keystone_home = os.getenv("KEYSTONE_HOME")
     38 -    qihse_python = importlib.util.find_spec("qihse") is not None
     39 +    qihse_home = _configured_home("QIHSE_HOME", BUNDLED_QIHSE_HOME)
     40 +    keystone_home = _configured_home("KEYSTONE_HOME", BUNDLED_KEYSTONE_HOME)
     41 +    qihse_python = importlib.util.find_spec("qihse") is not None or _has_bundled_python(qihse_home)
     42      qihse_library = bool(ctypes.util.find_library("qihse")) or _has_library(qihse_home, "libqihse.so")
        ⋮
     67          keystone_repo=KEYSTONE_REPO_URL,
     65 -        qihse_home=qihse_home,
     66 -        keystone_home=keystone_home,
     68 +        qihse_home=str(qihse_home) if qihse_home else None,
     69 +        keystone_home=str(keystone_home) if keystone_home else None,
     70          message=message,
        ⋮
     92
     90 -def _has_keystone_bridge(qihse_home: str | None, keystone_home: str | None) -> bool:
     93 +def _has_keystone_bridge(qihse_home: Path | str | None, keystone_home: Path | str | None) -> bool:
     94      candidates: list[Path] = []
        ⋮
    104      return any(path.exists() for path in candidates)
    105 +
    106 +
    107 +def _configured_home(env_name: str, bundled: Path) -> Path | None:
    108 +    value = os.getenv(env_name)
    109 +    if value:
    110 +        return Path(value)
    111 +    return bundled if bundled.exists() else None
    112 +
    113 +
    114 +def _has_bundled_python(home: Path | str | None) -> bool:
    115 +    if not home:
    116 +        return False
    117 +    return (Path(home) / "python" / "qihse" / "__init__.py").exists()

  └ zeropain/database/qihse_backend.py (+13 -0)
     7  import os
     8 +import sys
     9  from pathlib import Path
       ⋮
    18      def __init__(self, path: str | None = None):
    19 +        _prepare_qihse_import_path()
    20          import qihse
       ⋮
    61      return int.from_bytes(digest[:8], byteorder="big", signed=False)
    62 +
    63 +
    64 +def _prepare_qihse_import_path() -> None:
    65 +    status = database_backend_status()
    66 +    if not status.qihse_home:
    67 +        return
    68 +    python_path = Path(status.qihse_home) / "python"
    69 +    if python_path.exists():
    70 +        python_path_text = str(python_path)
    71 +        if python_path_text not in sys.path:
    72 +            sys.path.insert(0, python_path_text)

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• The repo now has a repeatable native build script and tests that exercise the bundled build when present. I’m setting executable permissions and
  running native smoke checks plus the regular suite.

• Ran chmod +x scripts/build_native_backends.sh && LD_LIBRARY_PATH=/fast/Main\ Workspace/ZEROPAIN/third_party/QIHSE:$LD_LIBRARY_PATH third_party/
  │ KEYSTONE/bin/test_core_native
  └ Running Enhanced KEYSTONE Test Suite
    =======================================
    … +22 lines (ctrl + t to view transcript)
    🎉 All Enhanced KEYSTONE tests passed!
    KEYSTONE-native improvements successfully integrated.

• Ran LD_LIBRARY_PATH=/fast/Main\ Workspace/ZEROPAIN/third_party/QIHSE:$LD_LIBRARY_PATH third_party/KEYSTONE/bin/test_auto_backend
  └ ASSERTION FAILED: decision.decision_source == KEYSTONE_DECISION_SOURCE_FAST_PATH at tests/test_auto_backend.c:228 in
    test_large_single_thread_batch_uses_scalar

• Ran ZEROPAIN_DB_BACKEND=qihse QIHSE_HOME=/fast/Main\ Workspace/ZEROPAIN/third_party/QIHSE KEYSTONE_HOME=/fast/Main\ Workspace/ZEROPAIN/third_party/
  │ KEYSTONE QIHSE_DB_PATH=/tmp/zeropain-qihse-full.kv python - <<'PY'
  │ from zeropain.database.backends import database_backend_status
  │ … +4 lines
  └
    [QIHSE QDD] GeoIP databases not found or incomplete.
    … +10 lines (ctrl + t to view transcript)
    Workspace/ZEROPAIN/third_party/QIHSE', 'keystone_home': '/fast/Main Workspace/ZEROPAIN/third_party/KEYSTONE', 'message': 'QIHSE backend ready'}
    True

──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• QIHSE/KEYSTONE smoke wiring works, and KEYSTONE core native tests pass. One upstream KEYSTONE auto-routing test fails on this CPU because its
  expected decision source differs from the compiled router path; I’m checking whether that is a build-flag issue or an upstream assertion mismatch
  before calling verification complete.

• Ran LD_LIBRARY_PATH=/fast/Main\ Workspace/ZEROPAIN/third_party/QIHSE:$LD_LIBRARY_PATH third_party/KEYSTONE/bin/test_enhanced
  └ 🧪 DSMIL KEYSTONE Integration Test Suite
    ==========================================
    … +26 lines (ctrl + t to view transcript)
    ✅ All integration tests passed!
    KEYSTONE is successfully integrated into DSMIL.

• Ran LD_LIBRARY_PATH=/fast/Main\ Workspace/ZEROPAIN/third_party/QIHSE:$LD_LIBRARY_PATH third_party/KEYSTONE/bin/test_performance_fix
  └ 🧪 Verification of Performance Fix
    =================================
    … +6 lines (ctrl + t to view transcript)

    ✅ All performance fix tests passed!

• Explored
  └ Read test_auto_backend.c
    Search DECISION_SOURCE|FAST_PATH|decision_source|large_single_thread in tests
    Read keystone.c
    Search calibr|FAST_PATH|threshold|num_threads|thread_count|batch_chunk in keystone.c


› Ensure main launcher builds and installs alldeps

