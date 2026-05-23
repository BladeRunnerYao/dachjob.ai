data "google_project" "project" {
  project_id = var.project_id
}

# API service account — used by Cloud Run for the FastAPI backend
resource "google_service_account" "api" {
  account_id   = "${var.name_prefix}-api-sa"
  display_name = "${var.name_prefix} API Service Account"
}

resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_storage_object_user" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "api_cloudtrace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.api.email}"
}

# Frontend service account — minimal permissions
resource "google_service_account" "frontend" {
  account_id   = "${var.name_prefix}-frontend-sa"
  display_name = "${var.name_prefix} Frontend Service Account"
}

# Worker service account — used by GKE for the Celery worker
resource "google_service_account" "worker" {
  account_id   = "${var.name_prefix}-worker-sa"
  display_name = "${var.name_prefix} Worker Service Account"
}

resource "google_project_iam_member" "worker_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

resource "google_project_iam_member" "worker_storage_object_user" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.worker.email}"
}

# Terraform / CI service account (created here, used by GitHub Actions)
resource "google_service_account" "terraform" {
  account_id   = "${var.name_prefix}-terraform-sa"
  display_name = "${var.name_prefix} Terraform Service Account"
}

resource "google_project_iam_member" "terraform_roles" {
  for_each = toset([
    "roles/editor",
    "roles/iam.securityAdmin",
    "roles/secretmanager.admin",
    "roles/storage.admin",
    "roles/run.admin",
    "roles/container.admin",
    "roles/compute.networkAdmin",
    "roles/cloudsql.admin",
    "roles/redis.admin",
    "roles/serviceusage.serviceUsageAdmin",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.terraform.email}"
}

# Workload Identity for GKE — applied manually after GKE cluster is created
# resource "google_service_account_iam_member" "worker_workload_identity" {
#   service_account_id = google_service_account.worker.name
#   role               = "roles/iam.workloadIdentityUser"
#   member             = "serviceAccount:${var.project_id}.svc.id.goog[celery-worker/worker]"
# }
