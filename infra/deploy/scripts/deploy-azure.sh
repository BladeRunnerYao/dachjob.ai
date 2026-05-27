#!/usr/bin/env bash
set -euo pipefail

#
# Deploy to Azure Container Apps.
#
# Usage: deploy-azure.sh <target> <api_image> <frontend_image> <worker_image>
#
# target: one of api, frontend, worker, all
#
# Reads env vars:
#   AZURE_RESOURCE_GROUP, AZURE_CONTAINER_APP_ENV, AZURE_API_NAME,
#   AZURE_FRONTEND_NAME, AZURE_WORKER_NAME, AZURE_API_URL, AZURE_FRONTEND_URL
#
# The caller is responsible for Azure authentication (az login) before calling
# this script.
#

target="$1"
api_image="$2"
frontend_image="$3"
worker_image="$4"

deploy_api() {
  echo "::group::Deploy API to Azure Container Apps"
  : "${AZURE_API_NAME:?AZURE_API_NAME is required}"
  : "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
  az containerapp update \
    --name "${AZURE_API_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --image "${api_image}" \
    --set-env-vars "CORS_ORIGINS=${AZURE_FRONTEND_URL:-}" \
    --output none
  echo "::endgroup::"
}

deploy_frontend() {
  echo "::group::Deploy frontend to Azure Container Apps"
  : "${AZURE_FRONTEND_NAME:?AZURE_FRONTEND_NAME is required}"
  : "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
  az containerapp update \
    --name "${AZURE_FRONTEND_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --image "${frontend_image}" \
    --set-env-vars "NEXT_PUBLIC_API_BASE_URL=${AZURE_API_URL:-} INTERNAL_API_BASE_URL=${AZURE_API_URL:-}" \
    --output none
  echo "::endgroup::"
}

deploy_worker() {
  echo "::group::Deploy worker to Azure Container Apps"
  : "${AZURE_WORKER_NAME:?AZURE_WORKER_NAME is required}"
  : "${AZURE_RESOURCE_GROUP:?AZURE_RESOURCE_GROUP is required}"
  az containerapp update \
    --name "${AZURE_WORKER_NAME}" \
    --resource-group "${AZURE_RESOURCE_GROUP}" \
    --image "${worker_image}" \
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
  all)
    deploy_api
    deploy_frontend
    deploy_worker
    ;;
  *)
    echo "Unknown target: ${target}"
    echo "Usage: deploy-azure.sh <target> <api_image> <frontend_image> <worker_image>"
    echo "  target: api | frontend | worker | all"
    exit 1
    ;;
esac
