#!/usr/bin/env bash

# Source this file from your shell to expose the local dachjob.ai URLs:
#   source scripts/local-env.sh

export DACHJOB_WEB_PORT="${DACHJOB_WEB_PORT:-3000}"
export DACHJOB_API_PORT="${DACHJOB_API_PORT:-8000}"
export DACHJOB_MINIO_PORT="${DACHJOB_MINIO_PORT:-9000}"
export DACHJOB_MINIO_CONSOLE_PORT="${DACHJOB_MINIO_CONSOLE_PORT:-9001}"

export DACHJOB_HOST="${DACHJOB_HOST:-localhost}"

export DACHJOB_WEB_URL="http://${DACHJOB_HOST}:${DACHJOB_WEB_PORT}"
export DACHJOB_JOBS_URL="${DACHJOB_WEB_URL}/jobs"
export DACHJOB_API_URL="http://${DACHJOB_HOST}:${DACHJOB_API_PORT}"
export DACHJOB_API_HEALTH_URL="${DACHJOB_API_URL}/api/health"
export DACHJOB_API_DOCS_URL="${DACHJOB_API_URL}/docs"
export DACHJOB_MINIO_URL="http://${DACHJOB_HOST}:${DACHJOB_MINIO_PORT}"
export DACHJOB_MINIO_CONSOLE_URL="http://${DACHJOB_HOST}:${DACHJOB_MINIO_CONSOLE_PORT}"

# Frontend tooling commonly reads this variable.
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-${DACHJOB_API_URL}}"

dachjob_urls() {
  printf '\n'
  printf 'dachjob.ai local URLs\n'
  printf '  Frontend:      %s\n' "${DACHJOB_WEB_URL}"
  printf '  Jobs:          %s\n' "${DACHJOB_JOBS_URL}"
  printf '  API:           %s\n' "${DACHJOB_API_URL}"
  printf '  API health:    %s\n' "${DACHJOB_API_HEALTH_URL}"
  printf '  API docs:      %s\n' "${DACHJOB_API_DOCS_URL}"
  printf '  MinIO:         %s\n' "${DACHJOB_MINIO_URL}"
  printf '  MinIO console: %s\n' "${DACHJOB_MINIO_CONSOLE_URL}"
  printf '\n'
}

dachjob_urls
