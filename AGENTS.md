# AGENTS.md

Instructions for AI coding assistants working on this project.

## Merge Rules

1. **Never merge until all CI jobs pass.** Do not merge a PR just because the Validate step is green — wait for all build, deploy, and smoke-test jobs to complete successfully. Never use `--admin` to bypass required status checks.

2. **Never merge without explicit permission.** After creating a PR, do not merge it yourself. Present the PR link and wait for the user to explicitly request a merge.

3. **Monitor CI and fix failures.** After pushing changes or creating a PR, actively watch both workflow runs (deploy-azure.yml and deploy-gcp.yml). If any job fails, investigate and fix the issue. Keep fixing until all jobs are green. Deploy failures on main are your responsibility to resolve.

## General Guidelines

- Use `git worktree` for changes — create a feature branch from main in a separate worktree, make changes there, then PR back to main.
- The platform deploys to both Google Cloud and Azure. Changes to CI workflows, Terraform, or deployment scripts may affect both clouds.
- Azure deployments sometimes experience transient OIDC federation failures (`No subscriptions found` during `az login`). The deploy workflow already includes retry logic for this.
