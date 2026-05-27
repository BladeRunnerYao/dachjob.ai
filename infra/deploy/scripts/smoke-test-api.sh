#!/usr/bin/env bash
set -euo pipefail

#
# Post-deploy smoke test for the dachjob.ai API and frontend.
#
# Usage:
#   SMOKE_TEST_MODE=minimal \
#   API_BASE_URL=https://api.example.com \
#   FRONTEND_URL=https://frontend.example.com \
#   SMOKE_TEST_EMAIL=<generated> \
#   SMOKE_TEST_PASSWORD=<password> \
#   bash smoke-test-api.sh
#
# Recommended email generation:
#   smoke+<cloud>-<github_run_id>-<github_run_attempt>@example.com
#
# SMOKE_TEST_MODE: minimal (required after every deploy) or full (optional).
#

: "${API_BASE_URL:?API_BASE_URL is required}"
: "${FRONTEND_URL:?FRONTEND_URL is required}"
: "${SMOKE_TEST_EMAIL:?SMOKE_TEST_EMAIL is required}"
: "${SMOKE_TEST_PASSWORD:?SMOKE_TEST_PASSWORD is required}"
: "${SMOKE_TEST_MODE:?SMOKE_TEST_MODE is required (minimal or full)}"

fail() {
  echo "::error::$1"
  exit 1
}

info() {
  echo "smoke: $1"
}

_json_field() {
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$1',''))"
}

_is_json() {
  python3 -c "import sys,json; json.load(sys.stdin)" >/dev/null 2>&1
}

_poll_background_task_if_needed() {
  local api_url="$1"
  local auth_header="$2"
  local response="$3"
  local label="$4"
  local max_attempts="$5"

  local task_id
  local task_status
  task_id="$(echo "${response}" | _json_field id 2>/dev/null || true)"
  task_status="$(echo "${response}" | _json_field status 2>/dev/null || true)"
  if [[ -z "${task_id}" || -z "${task_status}" ]]; then
    return 0
  fi

  info "${label} is background task ${task_id}, polling..."
  for _ in $(seq 1 "${max_attempts}"); do
    task_resp="$(curl -fsS "${api_url}/api/tasks/${task_id}" \
      -H "Content-Type: application/json" \
      -H "${auth_header}" || true)"
    task_status="$(echo "${task_resp}" | _json_field status 2>/dev/null || true)"
    [[ "${task_status}" == "succeeded" ]] && return 0
    [[ "${task_status}" == "failed" ]] && fail "${label} task failed"
    sleep 5
  done
  fail "${label} task did not succeed within timeout"
}

# ---------------------------------------------------------------------------
# Minimal smoke test (required after every deploy)
# ---------------------------------------------------------------------------

run_minimal() {
  local api_url="$1"
  local frontend_url="$2"
  local email="$3"
  local password="$4"

  info "Starting minimal smoke test"

  # 1. Health check
  info "GET /api/health"
  health_resp="$(curl -fsS "${api_url}/api/health")"
  health_status="$(echo "${health_resp}" | _json_field status)"
  [[ "${health_status}" == "ok" ]] || fail "Health check returned status=${health_status}"

  # 2. Version
  info "GET /api/version"
  version_resp="$(curl -fsS "${api_url}/api/version")"
  worker_enabled="$(echo "${version_resp}" | _json_field worker_enabled)"
  worker_fallback="$(echo "${version_resp}" | _json_field worker_fallback_to_sync)"
  echo "::notice::worker_enabled=${worker_enabled} worker_fallback_to_sync=${worker_fallback}"

  # 3. Register or login
  info "POST /api/auth/register (or login if exists)"
  register_resp="$(curl -fsS -X POST "${api_url}/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${email}\",\"password\":\"${password}\",\"name\":\"Smoke Test User\"}" 2>/dev/null || true)"

  token=""
  if echo "${register_resp}" | _is_json; then
    token="$(echo "${register_resp}" | _json_field token 2>/dev/null || true)"
    [[ -n "${token}" ]] && info "Registered new smoke test user"
  fi
  if [[ -z "${token}" ]]; then
    info "User exists, logging in"
    login_resp="$(curl -fsS -X POST "${api_url}/api/auth/login" \
      -H "Content-Type: application/json" \
      -d "{\"email\":\"${email}\",\"password\":\"${password}\"}")"
    token="$(echo "${login_resp}" | _json_field token)"
  fi
  [[ -n "${token}" ]] || fail "Failed to obtain auth token"

  auth_header="Authorization: Bearer ${token}"

  # 4. Auth me
  info "GET /api/auth/me"
  me_resp="$(curl -fsS "${api_url}/api/auth/me" -H "Content-Type: application/json" -H "${auth_header}")"
  me_email="$(echo "${me_resp}" | _json_field email)"
  [[ -n "${me_email}" ]] || fail "/api/auth/me did not return email"

  # 5. Upload CV
  info "POST /api/profile/cv"
  cv_resp="$(curl -fsS -X POST "${api_url}/api/profile/cv" \
    -H "Content-Type: application/json" \
    -H "${auth_header}" \
    -d '{"raw_cv_md":"# Smoke Test Candidate\n\n## Experience\n- Built CI/CD pipelines at Example Corp\n\n## Skills\n- Python, TypeScript, Docker, Kubernetes\n\n## Education\n- B.Sc. Computer Science"}' 2>/dev/null || true)"
  if echo "${cv_resp}" | _is_json; then
    info "CV uploaded"
  else
    info "CV upload may already exist, continuing"
  fi

  # 6. Create job
  info "POST /api/jobs"
  job_resp="$(curl -fsS -X POST "${api_url}/api/jobs" \
    -H "Content-Type: application/json" \
    -H "${auth_header}" \
    -d "{\"title\":\"Smoke Test Job - ${RANDOM}\",\"company\":\"Smoke Test GmbH\",\"raw_jd\":\"# Software Engineer\n\n## Requirements\n- Python\n- Docker\n- Kubernetes\n\n## Nice to have\n- TypeScript\"}")"
  job_id="$(echo "${job_resp}" | _json_field id)"
  [[ -n "${job_id}" ]] || fail "Failed to create job posting"

  # 7. List jobs
  info "GET /api/jobs?limit=5&offset=0"
  jobs_resp="$(curl -fsS "${api_url}/api/jobs?limit=5&offset=0" \
    -H "Content-Type: application/json" \
    -H "${auth_header}")"
  jobs_total="$(echo "${jobs_resp}" | _json_field total)"
  [[ -n "${jobs_total}" ]] || fail "Job listing returned no total field"

  # 8. Get job detail
  info "GET /api/jobs/${job_id}"
  job_detail="$(curl -fsS "${api_url}/api/jobs/${job_id}" \
    -H "Content-Type: application/json" \
    -H "${auth_header}")"
  job_detail_id="$(echo "${job_detail}" | _json_field id)"
  [[ "${job_detail_id}" == "${job_id}" ]] || fail "Job detail id mismatch"

  # 9. List applications
  info "GET /api/applications"
  apps_resp="$(curl -fsS "${api_url}/api/applications" \
    -H "Content-Type: application/json" \
    -H "${auth_header}")"
  apps_type="$(echo "${apps_resp}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(type(d).__name__)")"
  [[ "${apps_type}" == "list" ]] || fail "Applications did not return a list"

  # 10. Frontend URL
  info "GET ${frontend_url}"
  frontend_http_code="$(curl -sS -o /dev/null -w "%{http_code}" -L "${frontend_url}")"
  [[ "${frontend_http_code}" =~ ^[23] ]] || fail "Frontend returned HTTP ${frontend_http_code}"

  # 11. Login page
  info "GET ${frontend_url}/login"
  login_http_code="$(curl -sS -o /dev/null -w "%{http_code}" -L "${frontend_url}/login")"
  [[ "${login_http_code}" =~ ^[23] ]] || fail "Login page returned HTTP ${login_http_code}"

  echo "::notice::Minimal smoke test passed | job_id=${job_id} | token_ok=true | frontend_http=${frontend_http_code} | login_http=${login_http_code}"
  echo "SMOKE_PASSED=true" >> "${GITHUB_OUTPUT:-/dev/null}"
}

# ---------------------------------------------------------------------------
# Full smoke test (optional — includes LLM, PDF, workers)
# ---------------------------------------------------------------------------

run_full() {
  local api_url="$1"
  local email="$2"
  local password="$3"

  info "Starting full smoke test (extends minimal)"

  login_resp="$(curl -fsS -X POST "${api_url}/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${email}\",\"password\":\"${password}\"}")"
  token="$(echo "${login_resp}" | _json_field token)"
  [[ -n "${token}" ]] || fail "Failed to obtain auth token for full smoke test"
  auth_header="Authorization: Bearer ${token}"

  # Create a new job for full test
  job_resp="$(curl -fsS -X POST "${api_url}/api/jobs" \
    -H "Content-Type: application/json" \
    -H "${auth_header}" \
    -d "{\"title\":\"Full Smoke Test Job\",\"company\":\"Smoke Full GmbH\",\"raw_jd\":\"# Senior Engineer\n\n## Requirements\n- Python\n- Docker\n- CI/CD\n\n## Nice to have\n- Kubernetes\"}")"
  job_id="$(echo "${job_resp}" | _json_field id)"

  # 1. Parse job
  info "POST /api/jobs/${job_id}/parse"
  parse_resp="$(curl -fsS -X POST "${api_url}/api/jobs/${job_id}/parse" \
    -H "Content-Type: application/json" \
    -H "${auth_header}" \
    -d '{}')"
  _poll_background_task_if_needed "${api_url}" "${auth_header}" "${parse_resp}" "Job parse" 60

  # 2. Match
  info "POST /api/jobs/${job_id}/match"
  match_resp="$(curl -fsS -X POST "${api_url}/api/jobs/${job_id}/match" \
    -H "Content-Type: application/json" \
    -H "${auth_header}" \
    -d '{}')"
  _poll_background_task_if_needed "${api_url}" "${auth_header}" "${match_resp}" "Match" 60

  # 3. Resume
  info "POST /api/jobs/${job_id}/resume"
  resume_resp="$(curl -fsS -X POST "${api_url}/api/jobs/${job_id}/resume" \
    -H "Content-Type: application/json" \
    -H "${auth_header}" \
    -d '{}')"
  _poll_background_task_if_needed "${api_url}" "${auth_header}" "${resume_resp}" "Resume" 120

  # Find the artifact
  artifact_resp="$(curl -fsS "${api_url}/api/jobs/${job_id}/resume" \
    -H "Content-Type: application/json" \
    -H "${auth_header}")"
  artifact_id="$(echo "${artifact_resp}" | _json_field id)"
  [[ -n "${artifact_id}" ]] || fail "No resume artifact found"

  # 4. Resume HTML
  info "GET /api/resumes/${artifact_id}/html"
  html_code="$(curl -sS -o /dev/null -w "%{http_code}" "${api_url}/api/resumes/${artifact_id}/html" -H "${auth_header}")"
  [[ "${html_code}" == "200" ]] || fail "Resume HTML returned HTTP ${html_code}"

  # 5. Resume PDF
  info "GET /api/resumes/${artifact_id}/pdf"
  pdf_code="$(curl -sS -o /dev/null -w "%{http_code}" "${api_url}/api/resumes/${artifact_id}/pdf" -H "${auth_header}")"
  [[ "${pdf_code}" == "200" ]] || fail "Resume PDF returned HTTP ${pdf_code}"

  # 6. LLM runs
  info "GET /api/llm-runs?limit=5"
  llm_resp="$(curl -fsS "${api_url}/api/llm-runs?limit=5" \
    -H "Content-Type: application/json" \
    -H "${auth_header}")"
  llm_total="$(echo "${llm_resp}" | _json_field total)"
  [[ -n "${llm_total}" ]] || fail "LLM runs listing returned no total field"

  echo "::notice::Full smoke test passed | job_id=${job_id} | artifact_id=${artifact_id}"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

echo "## Smoke Test" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "| Item | Value |" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "| --- | --- |" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "| API URL | ${API_BASE_URL} |" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "| Frontend URL | ${FRONTEND_URL} |" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "| Mode | ${SMOKE_TEST_MODE} |" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"

run_minimal "${API_BASE_URL}" "${FRONTEND_URL}" "${SMOKE_TEST_EMAIL}" "${SMOKE_TEST_PASSWORD}"

if [[ "${SMOKE_TEST_MODE}" == "full" ]]; then
  run_full "${API_BASE_URL}" "${SMOKE_TEST_EMAIL}" "${SMOKE_TEST_PASSWORD}"
fi

echo "| Status | PASSED |" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "::notice::Smoke test complete | mode=${SMOKE_TEST_MODE}"
