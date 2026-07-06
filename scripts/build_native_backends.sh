#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THIRD_PARTY_DIR="${ROOT_DIR}/third_party"
QIHSE_DIR="${THIRD_PARTY_DIR}/QIHSE"
KEYSTONE_DIR="${THIRD_PARTY_DIR}/KEYSTONE"

mkdir -p "${THIRD_PARTY_DIR}"

if [[ ! -d "${QIHSE_DIR}/.git" ]]; then
  git clone https://github.com/SWORDIntel/QIHSE.git "${QIHSE_DIR}"
fi

if [[ ! -d "${KEYSTONE_DIR}/.git" ]]; then
  git clone https://github.com/SWORDIntel/KEYSTONE.git "${KEYSTONE_DIR}"
fi

git -C "${QIHSE_DIR}" submodule update --init --recursive

make -C "${QIHSE_DIR}" lib-ctypes \
  QIHSE_ENABLE_AVX2=1 \
  QIHSE_ENABLE_AVX512=0 \
  QIHSE_ENABLE_AVX_VNNI=0 \
  QIHSE_ENABLE_AMX=0

make -C "${KEYSTONE_DIR}" clean >/dev/null 2>&1 || true
make -C "${KEYSTONE_DIR}" tests \
  KEYSTONE_ENABLE_QIHSE_BRIDGE=1 \
  QIHSE_ROOT="${QIHSE_DIR}" \
  KEYSTONE_ENABLE_AVX2=1 \
  KEYSTONE_ENABLE_AVX512=0 \
  KEYSTONE_ENABLE_FORTRAN=0 \
  KEYSTONE_ENABLE_CUDA=0 \
  KEYSTONE_ENABLE_TAR_ZST=0

echo "QIHSE_HOME=${QIHSE_DIR}"
echo "KEYSTONE_HOME=${KEYSTONE_DIR}"
echo "LD_LIBRARY_PATH=${QIHSE_DIR}:\${LD_LIBRARY_PATH:-}"
