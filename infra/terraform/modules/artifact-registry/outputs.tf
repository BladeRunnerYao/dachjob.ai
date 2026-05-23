output "api_repo" {
  description = "Full Docker image URL for the API repository"
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.api.repository_id}"
}

output "frontend_repo" {
  description = "Full Docker image URL for the frontend repository"
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.frontend.repository_id}"
}

output "worker_repo" {
  description = "Full Docker image URL for the worker repository"
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.worker.repository_id}"
}

output "repositories" {
  description = "Map of repository names to their IDs"
  value = {
    api      = google_artifact_registry_repository.api.name
    frontend = google_artifact_registry_repository.frontend.name
    worker   = google_artifact_registry_repository.worker.name
  }
}
