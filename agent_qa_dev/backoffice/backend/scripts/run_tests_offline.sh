#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
VENV_PATH="${BACKOFFICE_TEST_VENV_PATH:-${BACKEND_DIR}/.venv-test}"
REQ_FILE="${BACKEND_DIR}/requirements-test.txt"
DB_PATH="${BACKOFFICE_DB_PATH:-${BACKEND_DIR}/backoffice_test.db}"
WHEELHOUSE="${BACKOFFICE_WHEELHOUSE:-}"
INDEX_URL="${BACKOFFICE_PIP_INDEX_URL:-}"
EXTRA_INDEX_URL="${BACKOFFICE_PIP_EXTRA_INDEX_URL:-}"
TRUSTED_HOST="${BACKOFFICE_PIP_TRUSTED_HOST:-}"

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "[error] requirements file not found: ${REQ_FILE}" >&2
  exit 1
fi

if [[ -z "${WHEELHOUSE}" && -z "${INDEX_URL}" ]]; then
  echo "[error] 오프라인/사내 미러 설정이 필요합니다." >&2
  echo "  - BACKOFFICE_WHEELHOUSE=/path/to/wheels  또는" >&2
  echo "  - BACKOFFICE_PIP_INDEX_URL=https://your-internal-pypi/simple" >&2
  exit 1
fi

python3 -m venv "${VENV_PATH}"
"${VENV_PATH}/bin/python" -m pip install -U pip

if [[ -n "${WHEELHOUSE}" ]]; then
  if [[ ! -d "${WHEELHOUSE}" ]]; then
    echo "[error] wheelhouse directory not found: ${WHEELHOUSE}" >&2
    exit 1
  fi
  echo "[info] installing deps from wheelhouse: ${WHEELHOUSE}"
  "${VENV_PATH}/bin/python" -m pip install --no-index --find-links "${WHEELHOUSE}" -r "${REQ_FILE}"
else
  echo "[info] installing deps from internal index: ${INDEX_URL}"
  if [[ -n "${TRUSTED_HOST}" ]]; then
    PIP_INDEX_URL="${INDEX_URL}" \
    PIP_EXTRA_INDEX_URL="${EXTRA_INDEX_URL}" \
    PIP_TRUSTED_HOST="${TRUSTED_HOST}" \
    "${VENV_PATH}/bin/python" -m pip install -r "${REQ_FILE}"
  else
    PIP_INDEX_URL="${INDEX_URL}" \
    PIP_EXTRA_INDEX_URL="${EXTRA_INDEX_URL}" \
    "${VENV_PATH}/bin/python" -m pip install -r "${REQ_FILE}"
  fi
fi

cd "${BACKEND_DIR}"
BACKOFFICE_DB_PATH="${DB_PATH}" "${VENV_PATH}/bin/python" -m pytest -q "$@"
