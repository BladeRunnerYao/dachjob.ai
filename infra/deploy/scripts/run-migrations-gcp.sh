#!/usr/bin/env bash
set -euo pipefail

#
# Run database migrations on GCP via Cloud Run jobs.
#
# Usage: run-migrations-gcp.sh <api_image>
#
# Reads env vars:
#   PROJECT_ID, REGION, MIGRATION_JOB_NAME, API_SERVICE_ACCOUNT,
#   CLOUD_SQL_CONNECTION_NAME, VPC_CONNECTOR, REDIS_URL, REDIS_ENABLED,
#   GCS_BUCKET, GOOGLE_CLOUD_PROJECT
#
# Required secrets (in GCP Secret Manager):
#   dachjob-dev-db-password, dachjob-dev-jwt-secret-key,
#   dachjob-dev-openrouter-api-key, dachjob-dev-deepseek-api-key
#

: "${PROJECT_ID:?PROJECT_ID is required}"
: "${REGION:?REGION is required}"
: "${MIGRATION_JOB_NAME:?MIGRATION_JOB_NAME is required}"
: "${API_SERVICE_ACCOUNT:?API_SERVICE_ACCOUNT is required}"
: "${CLOUD_SQL_CONNECTION_NAME:?CLOUD_SQL_CONNECTION_NAME is required}"
: "${VPC_CONNECTOR:?VPC_CONNECTOR is required}"
: "${REDIS_URL:?REDIS_URL is required}"
: "${GCS_BUCKET:?GCS_BUCKET is required}"
: "${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT is required}"

api_image="$1"

echo "::group::Deploy Cloud Run migration job"
gcloud run jobs deploy "${MIGRATION_JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${api_image}" \
  --service-account="${API_SERVICE_ACCOUNT}" \
  --set-cloudsql-instances="${CLOUD_SQL_CONNECTION_NAME}" \
  --vpc-connector="${VPC_CONNECTOR}" \
  --vpc-egress=private-ranges-only \
  --command=alembic \
  --args=-c,app/db/migrations/alembic.ini,upgrade,head \
  --set-env-vars="APP_ENV=production,CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION_NAME},DATABASE_USER=postgres,DATABASE_NAME=dachjob,REDIS_URL=${REDIS_URL},REDIS_ENABLED=${REDIS_ENABLED},S3_ENDPOINT_URL=https://storage.googleapis.com,S3_BUCKET_NAME=${GCS_BUCKET},GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT},LLM_PROVIDER=deepseek" \
  --update-secrets="DATABASE_PASSWORD=dachjob-dev-db-password:latest,JWT_SECRET=dachjob-dev-jwt-secret-key:latest,SECRET_KEY=dachjob-dev-jwt-secret-key:latest,OPENROUTER_API_KEY=dachjob-dev-openrouter-api-key:latest,DEEPSEEK_API_KEY=dachjob-dev-deepseek-api-key:latest"
echo "::endgroup::"

echo "::group::Execute migration job"
gcloud run jobs execute "${MIGRATION_JOB_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --wait
echo "::endgroup::"
