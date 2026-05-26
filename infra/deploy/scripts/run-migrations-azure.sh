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
# The caller is responsible for Azure authentication (az login) before calling
# this script.
#

: "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
: "${AZURE_CONTAINER_APP_ENV:?AZURE_CONTAINER_APP_ENV is required}"
: "${AZURE_MIGRATION_JOB_NAME:?AZURE_MIGRATION_JOB_NAME is required}"
: "${AZURE_ACR_NAME:?AZURE_ACR_NAME is required}"

api_image="$1"

echo "::group::Run database migrations on Azure"
ACR_PASS=$(az acr credential show -n "${AZURE_ACR_NAME}" --query "passwords[0].value" -o tsv 2>/dev/null || true)

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
  --output none 2>/dev/null || true

az containerapp job start \
  --name "${AZURE_MIGRATION_JOB_NAME}" \
  --resource-group "${AZURE_RESOURCE_GROUP}" \
  --output none
echo "::endgroup::"
