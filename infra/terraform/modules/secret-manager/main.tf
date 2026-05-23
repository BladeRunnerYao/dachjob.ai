# Secret Manager module — creates empty secrets for manual population.
# The actual secret values are set via GitHub Actions or gcloud CLI.

resource "google_secret_manager_secret" "openrouter_api_key" {
  secret_id = "${var.name_prefix}-openrouter-api-key"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "deepseek_api_key" {
  secret_id = "${var.name_prefix}-deepseek-api-key"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "jwt_secret_key" {
  secret_id = "${var.name_prefix}-jwt-secret-key"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "google_oauth_client_id" {
  secret_id = "${var.name_prefix}-google-oauth-client-id"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "google_oauth_client_secret" {
  secret_id = "${var.name_prefix}-google-oauth-client-secret"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "random_id" "db_password" {
  byte_length = 16
}

resource "google_secret_manager_secret" "db_password" {
  secret_id = "${var.name_prefix}-db-password"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_id.db_password.b64_std
}
