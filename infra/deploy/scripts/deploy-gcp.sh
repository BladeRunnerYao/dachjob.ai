#!/usr/bin/env bash
set -euo pipefail

#
# Deploy to GCP Cloud Run & GKE.
#
# Usage: deploy-gcp.sh <target> <api_image> <frontend_image> <worker_image> <image_tag> <run_migrations>
#
# Reads env vars:
#   PROJECT_ID, REGION, GAR_LOCATION, API_SERVICE_NAME, FRONTEND_SERVICE_NAME,
#   MIGRATION_JOB_NAME, API_BASE_URL, FRONTEND_URL, GKE_CLUSTER_NAME, GKE_NAMESPACE,
#   CLOUD_SQL_CONNECTION_NAME, VPC_CONNECTOR, REDIS_HOST, REDIS_PORT, REDIS_URL,
#   REDIS_ENABLED, GCS_BUCKET, API_SERVICE_ACCOUNT, FRONTEND_SERVICE_ACCOUNT,
#   WORKER_SERVICE_ACCOUNT, DEPLOYER_SERVICE_ACCOUNT
#

target="$1"
api_image="$2"
frontend_image="$3"
worker_image="$4"
run_migrations="$5"

deploy_api() {
  echo "::group::Deploy API to Cloud Run"
  gcloud run deploy "${API_SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --image="${api_image}" \
    --service-account="${API_SERVICE_ACCOUNT}" \
    --port=8000 \
    --allow-unauthenticated \
    --add-cloudsql-instances="${CLOUD_SQL_CONNECTION_NAME}" \
    --vpc-connector="${VPC_CONNECTOR}" \
    --vpc-egress=private-ranges-only \
    --set-env-vars="APP_ENV=production,CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION_NAME},DATABASE_USER=postgres,DATABASE_NAME=dachjob,REDIS_URL=${REDIS_URL},REDIS_HOST=${REDIS_HOST},REDIS_PORT=${REDIS_PORT},REDIS_ENABLED=${REDIS_ENABLED},S3_ENDPOINT_URL=https://storage.googleapis.com,S3_BUCKET_NAME=${GCS_BUCKET},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},LLM_PROVIDER=vertex_ai,VERTEX_AI_PROJECT_ID=${PROJECT_ID},VERTEX_AI_LOCATION=global,CORS_ORIGINS=${FRONTEND_URL}" \
    --update-secrets="DATABASE_PASSWORD=dachjob-dev-db-password:latest,JWT_SECRET=dachjob-dev-jwt-secret-key:latest,SECRET_KEY=dachjob-dev-jwt-secret-key:latest,GEMINI_API_KEY=dachjob-dev-gemini-api-key:latest,RESEND_API_KEY=dachjob-dev-smtp-password:latest,S3_ACCESS_KEY_ID=dachjob-dev-s3-access-key:latest,S3_SECRET_ACCESS_KEY=dachjob-dev-s3-secret-key:latest"

  api_url="$(gcloud run services describe "${API_SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
  echo "api_url=${api_url}" >> "${GITHUB_OUTPUT}"
  echo "::endgroup::"
}

deploy_frontend() {
  echo "::group::Deploy frontend to Cloud Run"
  gcloud run deploy "${FRONTEND_SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --image="${frontend_image}" \
    --service-account="${FRONTEND_SERVICE_ACCOUNT}" \
    --port=3000 \
    --allow-unauthenticated \
    --set-env-vars="NODE_ENV=production,NEXT_PUBLIC_API_BASE_URL=${API_BASE_URL},INTERNAL_API_BASE_URL=${API_BASE_URL}"

  frontend_url="$(gcloud run services describe "${FRONTEND_SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
  echo "frontend_url=${frontend_url}" >> "${GITHUB_OUTPUT}"
  echo "::endgroup::"
}

deploy_worker() {
  echo "::group::Deploy worker to GKE"
  gcloud iam service-accounts add-iam-policy-binding "${WORKER_SERVICE_ACCOUNT}" \
    --project="${PROJECT_ID}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${GKE_NAMESPACE}/worker]" >/dev/null

  database_password="$(gcloud secrets versions access latest --secret=dachjob-dev-db-password --project="${PROJECT_ID}")"
  jwt_secret_key="$(gcloud secrets versions access latest --secret=dachjob-dev-jwt-secret-key --project="${PROJECT_ID}")"
  gemini_api_key="$(gcloud secrets versions access latest --secret=dachjob-dev-gemini-api-key --project="${PROJECT_ID}" 2>/dev/null || true)"
  database_url="postgresql+psycopg://postgres:${database_password}@localhost/dachjob?host=/cloudsql/${CLOUD_SQL_CONNECTION_NAME}"

  kubectl create namespace "${GKE_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -
  kubectl create secret generic worker-secrets \
    --namespace="${GKE_NAMESPACE}" \
    --from-literal=database_password="${database_password}" \
    --from-literal=database_url="${database_url}" \
    --from-literal=jwt_secret_key="${jwt_secret_key}" \
    --from-literal=gemini_api_key="${gemini_api_key}" \
    --dry-run=client -o yaml | kubectl apply -f -

  kubectl apply -f infra/k8s/celery-worker/deployment.yaml
  kubectl set image deployment/celery-worker \
    worker="${worker_image}" \
    --namespace="${GKE_NAMESPACE}"
  kubectl rollout status deployment/celery-worker --namespace="${GKE_NAMESPACE}" --timeout=300s
  echo "::endgroup::"
}

run_migrations_fn() {
  echo "::group::Run database migrations"
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
    --set-env-vars="APP_ENV=production,CLOUD_SQL_CONNECTION_NAME=${CLOUD_SQL_CONNECTION_NAME},DATABASE_USER=postgres,DATABASE_NAME=dachjob,REDIS_URL=${REDIS_URL},REDIS_ENABLED=${REDIS_ENABLED},S3_ENDPOINT_URL=https://storage.googleapis.com,S3_BUCKET_NAME=${GCS_BUCKET},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},LLM_PROVIDER=deepseek" \
    --update-secrets="DATABASE_PASSWORD=dachjob-dev-db-password:latest,JWT_SECRET=dachjob-dev-jwt-secret-key:latest,SECRET_KEY=dachjob-dev-jwt-secret-key:latest,OPENROUTER_API_KEY=dachjob-dev-openrouter-api-key:latest,DEEPSEEK_API_KEY=dachjob-dev-deepseek-api-key:latest"

  gcloud run jobs execute "${MIGRATION_JOB_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --wait
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
