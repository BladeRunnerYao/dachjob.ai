#!/usr/bin/env bash
# Deploy dachjob.ai to Cloudflare (Worker API + Pages Frontend)
# Usage: ./deploy.sh [api|frontend|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

component="${1:-all}"

deploy_api() {
    echo "==> Deploying Worker API..."
    cd "$SCRIPT_DIR/worker-api"
    npm ci
    npx wrangler deploy
    echo "==> Worker API deployed."
}

deploy_frontend() {
    echo "==> Building frontend..."
    cd "$ROOT_DIR/app/frontend"
    npm ci
    NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-https://dachjob-api.yaoyaoyaoyao.workers.dev}" npm run build
    echo "==> Deploying to Cloudflare Pages..."
    npx wrangler pages deploy out --project-name=dachjob-web
    echo "==> Frontend deployed."
}

migrate_db() {
    echo "==> Running D1 migrations..."
    cd "$SCRIPT_DIR/worker-api"
    npx wrangler d1 execute dachjob-db --remote --file=../migrations/0001_initial.sql
    echo "==> Migrations complete."
}

case "$component" in
    api)
        deploy_api
        ;;
    frontend)
        deploy_frontend
        ;;
    migrate)
        migrate_db
        ;;
    all)
        migrate_db
        deploy_api
        deploy_frontend
        ;;
    *)
        echo "Usage: $0 [api|frontend|migrate|all]"
        exit 1
        ;;
esac

echo "==> Done!"
