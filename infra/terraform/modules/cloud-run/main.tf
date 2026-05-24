resource "google_cloud_run_v2_service" "api" {
  name     = "${var.name_prefix}-api"
  location = var.region
  labels   = var.labels
  client   = "terraform"

  template {
    service_account                  = var.api_service_account_email
    timeout                          = "300s"
    max_instance_request_concurrency = 80

    vpc_access {
      connector = var.vpc_connector_id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [var.cloud_sql_connection_name]
      }
    }

    containers {
      image = var.api_image

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "DATABASE_URL"
        value = "postgresql+asyncpg://${var.api_service_account_email}/dachjob?host=/cloudsql/${var.cloud_sql_connection_name}"
      }
      env {
        name  = "CLOUD_SQL_CONNECTION_NAME"
        value = var.cloud_sql_connection_name
      }
      env {
        name  = "DATABASE_USER"
        value = "postgres"
      }
      env {
        name  = "DATABASE_NAME"
        value = "dachjob"
      }
      env {
        name = "DATABASE_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.db_password.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "REDIS_URL"
        value = "redis://${var.redis_host}:6379/0"
      }
      env {
        name  = "REDIS_HOST"
        value = var.redis_host
      }
      env {
        name  = "REDIS_PORT"
        value = "6379"
      }
      env {
        name  = "S3_ENDPOINT_URL"
        value = "https://storage.googleapis.com"
      }
      env {
        name  = "S3_BUCKET_NAME"
        value = var.gcs_bucket_name
      }
      env {
        name  = "S3_ACCESS_KEY_ID"
        value = ""
      }
      env {
        name  = "S3_SECRET_ACCESS_KEY"
        value = ""
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "LLM_PROVIDER"
        value = "gemini"
      }
      env {
        name = "JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = data.google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }

      ports {
        container_port = 8000
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
  }
}

resource "google_cloud_run_v2_service" "frontend" {
  name     = "${var.name_prefix}-frontend"
  location = var.region
  labels   = var.labels
  client   = "terraform"

  template {
    service_account = var.frontend_service_account_email
    timeout         = "60s"

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = var.frontend_image

      env {
        name  = "NEXT_PUBLIC_API_BASE_URL"
        value = google_cloud_run_v2_service.api.uri
      }
      env {
        name  = "INTERNAL_API_BASE_URL"
        value = google_cloud_run_v2_service.api.uri
      }
      env {
        name  = "NODE_ENV"
        value = "production"
      }

      ports {
        container_port = 3000
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "api_noauth" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "frontend_noauth" {
  name     = google_cloud_run_v2_service.frontend.name
  location = google_cloud_run_v2_service.frontend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Reference the secrets created in the secret-manager module
data "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "${var.name_prefix}-gemini-api-key"
}

data "google_secret_manager_secret" "jwt_secret" {
  secret_id = "${var.name_prefix}-jwt-secret-key"
}

data "google_secret_manager_secret" "db_password" {
  secret_id = "${var.name_prefix}-db-password"
}
