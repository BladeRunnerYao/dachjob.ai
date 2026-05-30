# CI and Deployment Workflows

Reusable local actions live under `.github/actions/`:

| Action | Purpose |
|---|---|
| `setup-backend` | Configures Python 3.12 and installs backend dev dependencies after the caller checks out the repo. |
| `setup-frontend` | Configures Node.js 26 and runs `npm ci` after the caller checks out the repo. |
| `docker-build-push` | Sets up Buildx and wraps `docker/build-push-action`. |
| `smoke-test` | Runs `infra/deploy/scripts/smoke-test-api.sh` with consistent API/frontend inputs. |

`terraform-drift.yml` runs weekly and can be dispatched manually. It runs `terraform plan -detailed-exitcode` only and never applies changes.
