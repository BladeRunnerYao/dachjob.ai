#!/usr/bin/env bash
set -euo pipefail

#
# Run database migrations on Azure via Container Apps jobs.
#
# Usage: run-migrations-azure.sh <api_image>
#
# Reads env vars:
#   AZURE_RESOURCE_GROUP, AZURE_CONTAINER_APP_ENV, AZURE_MIGRATION_JOB_NAME,
#   AZURE_ACR_NAME
#
# Optional for creating or refreshing job secrets:
#   AZURE_DATABASE_URL, AZURE_REDIS_URL, AZURE_STORAGE_CONNECTION_STRING
#
# The caller is responsible for Azure authentication (az login) before calling
# this script.
#

: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${AZURE_CONTAINER_APP_ENV:?AZURE_CONTAINER_APP_ENV is required}"
: "${AZURE_MIGRATION_JOB_NAME:?AZURE_MIGRATION_JOB_NAME is required}"
: "${AZURE_ACR_NAME:?AZURE_ACR_NAME is required}"

api_image="$1"

echo "::group::Run database migrations on Azure"

job_exists=false
if az containerapp job show \
  --name "${AZURE_MIGRATION_JOB_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --query name \
  -o tsv >/dev/null 2>&1; then
  job_exists=true
fi

secret_args=()
env_args=("APP_ENV=production")
if [[ -n "${AZURE_DATABASE_URL:-}" ]]; then
  secret_args+=("db-url=${AZURE_DATABASE_URL}")
  env_args+=("DATABASE_URL=secretref:db-url")
fi
if [[ -n "${AZURE_REDIS_URL:-}" ]]; then
  secret_args+=("redis-url=${AZURE_REDIS_URL}")
  env_args+=("REDIS_URL=secretref:redis-url" "REDIS_ENABLED=true")
fi
if [[ -n "${AZURE_STORAGE_CONNECTION_STRING:-}" ]]; then
  secret_args+=("storage-conn=${AZURE_STORAGE_CONNECTION_STRING}")
  env_args+=("AZURE_STORAGE_CONNECTION_STRING=secretref:storage-conn" "STORAGE_PROVIDER=azure_blob")
fi

secret_flags=()
if (( ${#secret_args[@]} > 0 )); then
  secret_flags=(--secrets "${secret_args[@]}")
fi

env_flags=()
if (( ${#env_args[@]} > 0 )); then
  env_flags=(--env-vars "${env_args[@]}")
fi

if [[ "${job_exists}" == "true" ]]; then
  if (( ${#secret_args[@]} > 0 )); then
    az containerapp job secret set \
      --name "${AZURE_MIGRATION_JOB_NAME}" \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --secrets "${secret_args[@]}" \
      --output none
  fi

  # Keep command/args immutable on update. Azure CLI can misparse job args that
  # begin with "-"; the job is created once with the Alembic command and later
  # deployments only need to refresh image and secrets. Environment variables
  # are set at job creation time and are not updatable via --env-vars on update.
  az containerapp job update \
    --name "${AZURE_MIGRATION_JOB_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --image "${api_image}" \
    --output none

  # Set environment variables via template --set (cross-version compatible)
  env_json=$(printf '%s\n' "${env_args[@]}" | jq -R -s -c '
    split("\n") | map(select(length > 0)) | map(
      capture("^(?<name>[^=]+)=(?<value>.*)$")
      | if .value | startswith("secretref:") then
          {name: .name, secretRef: (.value | sub("^secretref:"; ""))}
        else
          {name: .name, value: .value}
        end
    )
  ')
  if [[ -n "${env_json}" && "${env_json}" != "[]" ]]; then
    az containerapp job update \
      --name "${AZURE_MIGRATION_JOB_NAME}" \
      --resource-group "${AZURE_RESOURCE_GROUP}" \
      --set "template.containers[0].env=${env_json}" \
      --output none
  fi
else
  if [[ -z "${AZURE_DATABASE_URL:-}" ]]; then
    echo "::error::AZURE_DATABASE_URL is required when creating the Azure migration job."
    exit 1
  fi

  ACR_PASS=$(az acr credential show -n "${AZURE_ACR_NAME}" --query "passwords[0].value" -o tsv 2>/dev/null || true)
  if [[ -z "${ACR_PASS}" ]]; then
    echo "::error::ACR admin credentials are unavailable. Pre-create the migration job with managed identity, or enable a scoped registry credential for this dev workflow."
    exit 1
  fi

  az containerapp job create \
    --name "${AZURE_MIGRATION_JOB_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --environment "${AZURE_CONTAINER_APP_ENV}" \
    --image "${api_image}" \
    --registry-server "${AZURE_ACR_NAME}.azurecr.io" \
    --registry-username "${AZURE_ACR_NAME}" \
    --registry-password "${ACR_PASS}" \
    --command "alembic" \
    --args "-c" "app/db/migrations/alembic.ini" "upgrade" "head" \
    --trigger-type Manual \
    "${secret_flags[@]}" \
    "${env_flags[@]}" \
    --output none
fi

az containerapp job start \
  --name "${AZURE_MIGRATION_JOB_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --output none
echo "::endgroup::"
