#!/usr/bin/env bash
set -euo pipefail

#
# Deploy to Azure Container Apps.
#
# Usage: deploy-azure.sh <target> <api_image> <frontend_image> <worker_image> <image_tag> <run_migrations>
#
# Reads env vars:
#   AZURE_RESOURCE_GROUP, AZURE_CONTAINER_APP_ENV, AZURE_API_NAME,
#   AZURE_FRONTEND_NAME, AZURE_WORKER_NAME, AZURE_MIGRATION_JOB_NAME,
#   API_BASE_URL, and tfoutputs JSON exported from Terraform.
#

target="$1"
api_image="$2"
frontend_image="$3"
worker_image="$4"
run_migrations="$5"

deploy_api() {
  echo "::group::Deploy API to Azure Container Apps"
  az containerapp update \
    --name "${AZURE_API_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --image "${api_image}" \
    --output none
  echo "::endgroup::"
}

deploy_frontend() {
  echo "::group::Deploy frontend to Azure Container Apps"
  az containerapp update \
    --name "${AZURE_FRONTEND_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --image "${frontend_image}" \
    --output none
  echo "::endgroup::"
}

deploy_worker() {
  echo "::group::Deploy worker to Azure Container Apps"
  az containerapp update \
    --name "${AZURE_WORKER_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --image "${worker_image}" \
    --output none
  echo "::endgroup::"
}

run_migrations_fn() {
  echo "::group::Run database migrations on Azure"
  az containerapp job create \
    --name "${AZURE_MIGRATION_JOB_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --environment "${AZURE_CONTAINER_APP_ENV}" \
    --image "${api_image}" \
    --command "alembic" \
    --args "-c app/db/migrations/alembic.ini upgrade head" \
    --trigger-type Manual \
    --output none 2>/dev/null || true

  az containerapp job start \
    --name "${AZURE_MIGRATION_JOB_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --output none
  echo "::endgroup::"
}

case "${target}" in
  api)
    deploy_api
    ;;
  frontend)
    deploy_frontend
    ;;
  worker)
    deploy_worker
    ;;
  migrations)
    run_migrations_fn
    ;;
  all)
    deploy_api
    deploy_frontend
    deploy_worker
    if [[ "${run_migrations}" == "true" ]]; then
      run_migrations_fn
    fi
    ;;
  *)
    echo "Unknown target: ${target}"
    exit 1
    ;;
esac
