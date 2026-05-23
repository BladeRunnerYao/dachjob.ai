resource "google_sql_database_instance" "postgres" {
  name             = "${var.name_prefix}-postgres"
  database_version = "POSTGRES_16"
  region           = var.region
  labels           = var.labels

  settings {
    tier              = var.db_tier
    disk_size         = var.db_disk_size_gb
    disk_type         = "PD_SSD"
    availability_type = "ZONAL"

    backup_configuration {
      enabled                        = true
      start_time                     = "03:00"
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id

      authorized_networks {
        name  = "cloud-run-connector"
        value = "10.8.0.0/28"
      }
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }

  deletion_protection = false
}

resource "google_sql_database" "database" {
  name     = "dachjob"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "iam_user" {
  name     = "cloud-run-sa"
  instance = google_sql_database_instance.postgres.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}
