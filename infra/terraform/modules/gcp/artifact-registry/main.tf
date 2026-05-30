resource "google_artifact_registry_repository" "api" {
  repository_id = "${var.name_prefix}-api"
  format        = "DOCKER"
  location      = var.region
  labels        = var.labels

  docker_config {
    immutable_tags = false
  }
}

resource "google_artifact_registry_repository" "frontend" {
  repository_id = "${var.name_prefix}-frontend"
  format        = "DOCKER"
  location      = var.region
  labels        = var.labels

  docker_config {
    immutable_tags = false
  }
}

resource "google_artifact_registry_repository" "worker" {
  repository_id = "${var.name_prefix}-worker"
  format        = "DOCKER"
  location      = var.region
  labels        = var.labels

  docker_config {
    immutable_tags = false
  }
}
