#!/usr/bin/env bash
set -euo pipefail

# Bootstrap script for dachjob.ai GCP infrastructure.
# Run once to create the Terraform state bucket and set up the backend.

ENV="${1:-dev}"
PROJECT_ID="dachjob-ai-platform"
STATE_BUCKET="dachjob-${ENV}-terraform-state"

echo "=== Bootstrapping Terraform state for environment: ${ENV} ==="

# 1. Check if the state bucket already exists
if gsutil ls "gs://${STATE_BUCKET}" &>/dev/null 2>&1; then
  echo "Bucket gs://${STATE_BUCKET} already exists."
else
  echo "Creating state bucket gs://${STATE_BUCKET}..."
  gsutil mb -p "${PROJECT_ID}" -l "EUROPE-WEST1" "gs://${STATE_BUCKET}"
  gsutil versioning set on "gs://${STATE_BUCKET}"
  echo "Bucket created."
fi

# 2. Write backend configuration
TF_ROOT="infra/terraform/live/gcp/${ENV}"
BACKEND_CONF="${TF_ROOT}/backend.conf"
if [[ ! -d "${TF_ROOT}" ]]; then
  echo "Terraform root ${TF_ROOT} does not exist." >&2
  exit 1
fi

cat > "${BACKEND_CONF}" <<EOF
bucket = "${STATE_BUCKET}"
prefix = "${ENV}"
EOF
echo "Backend config written to ${BACKEND_CONF}"

# 3. Initialize Terraform with the backend
cd "${TF_ROOT}"
terraform init -backend-config=backend.conf
echo "Terraform initialized successfully."

echo ""
echo "=== Bootstrap complete ==="
echo "Next steps:"
echo "  1. Verify variables in ${TF_ROOT}/terraform.tfvars"
echo "  2. Run: cd ${TF_ROOT} && terraform plan"
echo "  3. Run: cd ${TF_ROOT} && terraform apply"
