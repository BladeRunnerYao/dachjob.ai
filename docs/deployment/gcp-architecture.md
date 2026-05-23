# GCP Deployment Architecture — dachjob.ai

## Comparison: Cloud Run vs GKE

### Cloud Run

| Aspect | Detail |
|--------|--------|
| **Type** | Serverless container platform |
| **Scaling** | Scales to zero when idle |
| **Pricing** | Pay per request + CPU/memory during request handling |
| **Management** | Zero cluster management |
| **Max request timeout** | 60 minutes |
| **Concurrency** | Multiple requests per container instance |

### GKE (Google Kubernetes Engine)

| Aspect | Detail |
|--------|--------|
| **Type** | Managed Kubernetes cluster |
| **Scaling** | Min nodes always running (even with Autopilot) |
| **Pricing** | Pay per node + workload (cluster has baseline cost) |
| **Management** | Node pool maintenance, upgrades, monitoring |
| **Capabilities** | Full K8s: Deployments, StatefulSets, CronJobs, DaemonSets |
| **Process types** | Supports long-running processes, event-driven workers |

### Which One for dachjob.ai?

**Recommendation: Hybrid — Cloud Run (API + Frontend) + GKE Autopilot or Compute Engine (Celery Worker)**

#### Why Cloud Run is better for the API and Frontend

1. **Cost efficiency** — Scales to zero when no one uses the app. With only €250 credits, every euro counts. A GKE cluster has a baseline node cost whether you use it or not.

2. **Simplicity** — No cluster to manage. No node upgrades, no networking plugins, no monitoring stack to set up. Deployment is `gcloud run deploy` with a container image.

3. **Built-in HTTPS & DNS** — Cloud Run provides automatic TLS certificates and custom domain mapping via Cloudflare or Google Domains.

4. **Fast iteration** — CI/CD pipeline is trivial: build image → push to Artifact Registry → deploy to Cloud Run.

#### Why GKE (or at least a persistent VM) is needed for the Celery Worker

Cloud Run is **request-driven** — it spins up containers only when an HTTP request arrives. The Celery worker is a **long-running process** that polls Redis for tasks. It cannot run on Cloud Run directly.

Options for the worker:

| Option | Pros | Cons |
|--------|------|------|
| **GKE Autopilot (small cluster)** | Full K8s flexibility; same cluster runs API + worker + cron jobs | Cluster baseline cost (~€15-30/month) |
| **Compute Engine (e2-micro, free tier)** | Cheapest option; simple to manage | No K8s benefits; manual setup |
| **Cloud Tasks** replaces Celery | Serverless; no worker to manage | Requires code changes; different semantics |
| **Cloud Run + polling** (workaround) | Avoids extra infrastructure | Anti-pattern; unreliable |

### Recommended Architecture

```
                                    ┌─────────────────┐
                                    │  Cloud Load     │
                                    │  Balancer       │
                                    └────────┬────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  Cloud Run       │
                                    │  (Next.js        │
                                    │   Frontend)      │
                                    └────────┬────────┘
                                             │ API calls
                                    ┌────────▼────────┐
                                    │  Cloud Run       │
                                    │  (FastAPI        │
                                    │   Backend)       │
                                    └────────┬────────┘
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              │                              │                              │
       ┌──────▼──────┐               ┌───────▼───────┐              ┌───────▼───────┐
       │  Cloud SQL   │               │  Cloud        │              │  Secret       │
       │  PostgreSQL  │               │  Storage (GCS)│              │  Manager      │
       │  + pgvector  │               │  (file store) │              │  (API keys)   │
       └──────────────┘               └───────────────┘              └───────────────┘
                                             │
                                    ┌────────▼────────┐
                                    │  Memorystore    │
                                    │  (Redis)        │
                                    └────────┬────────┘
                                             │
                              ┌──────────────▼──────────────┐
                              │  Cloud Run / GKE / Compute  │
                              │  Engine (Celery Worker)     │
                              └─────────────────────────────┘
```

### Service Map

| Component | Platform | Reason |
|-----------|----------|--------|
| **FastAPI Backend** | Cloud Run | Request-driven; scales to zero |
| **Next.js Frontend** | Cloud Run | Static + SSR; scales to zero |
| **Celery Worker** | GKE Autopilot (smallest config) or Compute Engine e2-micro | Needs persistent process |
| **PostgreSQL** | Cloud SQL | Managed; backups; pgvector support |
| **Redis** | Memorystore | Managed; Celery broker |
| **Object Storage** | Cloud Storage (GCS) | S3-compatible; cheap |
| **Secrets** | Secret Manager | Native GCP; IAM integration |
| **Docker Images** | Artifact Registry | Stores all container images (API, Frontend, Worker) |
| **Monitoring** | Cloud Monitoring + Cloud Logging | Built-in; dashboards + alerting |
| **DNS** | Cloud DNS | Custom domain + TLS (if needed) |
| **Identity** | IAM Service Accounts | Secure workload identity per component |

### Infrastructure as Code (Terraform)

```
infra/terraform/
├── versions.tf
├── backend.tf                   # State stored in GCS bucket
├── providers.tf
├── variables.tf
├── locals.tf
│
├── modules/
│   ├── artifact-registry/       # Docker image repositories
│   │   └── main.tf
│   ├── cloud-run/               # Cloud Run services (api, frontend)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── cloud-sql/               # PostgreSQL + pgvector
│   │   ├── main.tf
│   │   └── variables.tf
│   ├── memorystore/             # Redis
│   │   ├── main.tf
│   │   └── variables.tf
│   ├── cloud-storage/           # GCS buckets
│   │   └── main.tf
│   ├── secret-manager/          # API keys, secrets
│   │   └── main.tf
│   ├── gke/                     # GKE cluster (if needed for worker)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   ├── iam/                     # Service accounts & IAM bindings
│   │   └── main.tf
│   ├── cloud-dns/               # DNS zone + records (if custom domain)
│   │   └── main.tf
│   └── monitoring/              # Alerting policies + dashboards
│       └── main.tf
│
└── environments/
    └── dev/
        ├── terraform.tfvars
        └── backend.conf
```

### Deployment Pipeline (CI/CD)

1. Push to `main` branch
2. GitHub Actions (or Cloud Build) triggers:
   - Build Docker images for API, Frontend, Worker
   - Push to Artifact Registry
   - Deploy API + Frontend to Cloud Run
   - Update GKE deployment for Worker (or redeploy)
3. Terraform runs independently for infrastructure changes

### Cost Estimate (with credits)

| Service | Estimated Monthly Cost |
|---------|----------------------|
| Cloud Run (API + Frontend) | €5-15 (near-zero if idle) |
| Cloud SQL (smallest tier) | ~€10-20 |
| Memorystore (smallest) | ~€10-15 |
| Cloud Storage | ~€1-5 |
| GKE Autopilot (if used) | ~€15-30 |
| **Total** | **~€40-85/month** |

At €250 free credits, this gives approximately **3-6 months** of runway depending on usage.

### Secret Manager Usage

Secrets to store:
- `OPENROUTER_API_KEY`
- `DEEPSEEK_API_KEY` (fallback)
- `SECRET_KEY` (JWT signing)
- `SENTRY_DSN` (if used)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (OAuth)
- Database passwords

Access via Workload Identity (GKE) or direct binding (Cloud Run) — no secrets in environment variables or config files.

---

## Additional GCP Services — Needed or Not?

### Artifact Registry (Docker Image Registry)

**✅ Required.**

This is the equivalent of Azure Container Registry. Every Docker image (API, Frontend, Celery Worker) is built and pushed here before deployment.

- GCP's recommended registry (Container Registry `gcr.io` is deprecated)
- Each image lives in a repository: `europe-west1-docker.pkg.dev/dachjob-ai-platform/api`, `.../frontend`, `.../worker`
- Integrated with Cloud Run, GKE, Cloud Build, and IAM

### API Gateway / API Management

**❌ Not needed for now.**

An API Gateway (Apigee / Cloud API Gateway) adds rate limiting, client API keys, request transformation, and usage analytics. For dachjob.ai:

- There is a **single backend service** (FastAPI) consumed by its own frontend
- Cloud Run already handles HTTPS termination, authentication, and request routing
- No third-party API consumers that need rate limiting or API keys

**Revisit if**: you expose a public API for third-party integrations or need per-client usage billing.

### Cloud DNS

**✅ Required (if using a custom domain).**

- Cloud Run provides an auto-generated `*.run.app` URL
- For production at a custom domain (e.g. `dachjob.ai` or `app.dachjob.ai`), you need Cloud DNS to manage DNS records
- Cloud DNS integrates with Cloud Run's custom domain mapping (automatic TLS certificates)

**Without Cloud DNS**: you can still deploy and test on the `*.run.app` URL during development.

### Cloud Logging

**✅ Required (automatic, no extra setup).**

- Cloud Run and GKE automatically stream container stdout/stderr to Cloud Logging
- No additional configuration needed — it just works
- Essential for debugging: view logs per revision, filter by severity, export to BigQuery
- Integrated with Error Reporting (automatic error detection from logs)

### Cloud Monitoring

**✅ Recommended.**

- Pre-built dashboards for Cloud Run (request count, latency, CPU, memory, billable time)
- Alerting policies: e.g., alert when error rate > 5%, or when Cloud Run billable time exceeds a threshold
- Can monitor Cloud SQL, Memorystore, and GKE from the same console
- The project already includes Prometheus metrics in the API — Cloud Monitoring can scrape them via Google Cloud Managed Service for Prometheus

### IAM Service Accounts

**✅ Required (one per component).**

Service accounts provide secure identity for each component. No hardcoded keys or long-lived credentials.

| Service Account | Purpose | Permissions Needed |
|----------------|---------|-------------------|
| **Cloud Run API** | The FastAPI backend running on Cloud Run | Cloud SQL Client, Secret Manager Secret Accessor, Storage Object User |
| **Cloud Run Frontend** | The Next.js frontend | (minimal — only makes HTTP calls to API) |
| **GKE Node Pool** | The GKE cluster nodes | Artifact Registry Reader, Cloud SQL Client, Secret Manager Accessor, Monitoring Metric Writer |
| **Terraform** | Applied locally or in CI | Project Creator, Billing User, Service Usage Admin, and per-resource admin roles |
| **CI/CD (GitHub Actions)** | Push images + deploy | Artifact Registry Writer, Cloud Run Admin, GKE Developer |

**Workload Identity** (GKE) or **Direct IAM binding** (Cloud Run) assigns these service accounts to running workloads — no JSON keys to manage.

### Summary Table

| Service | Required? | Reason |
|---------|-----------|--------|
| Artifact Registry | ✅ Yes | Store all Docker images |
| API Gateway | ❌ No | Single backend; Cloud Run handles routing |
| Cloud DNS | ⚠️ Conditional | Only needed for custom domain |
| Cloud Logging | ✅ Yes | Automatic; essential for debugging |
| Cloud Monitoring | ✅ Recommended | Dashboards + cost/error alerts |
| IAM Service Accounts | ✅ Yes | Secure identity for every component |
| Secret Manager | ✅ Yes | API keys, DB passwords, JWT secret |
