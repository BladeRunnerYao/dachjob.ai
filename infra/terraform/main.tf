locals {
  name_prefix = "dachjob-${var.environment}"

  common_labels = {
    app         = "dachjob"
    environment = var.environment
    managed-by  = "terraform"
  }
}

module "networking" {
  source = "./modules/networking"

  name_prefix = local.name_prefix
  region      = var.region
  labels      = local.common_labels
}

module "artifact-registry" {
  source = "./modules/artifact-registry"

  name_prefix = local.name_prefix
  region      = var.region
  project_id  = var.project_id
  labels      = local.common_labels
}

module "cloud-sql" {
  source = "./modules/cloud-sql"

  name_prefix     = local.name_prefix
  region          = var.region
  db_tier         = var.db_tier
  db_disk_size_gb = var.db_disk_size_gb
  network_id               = module.networking.network_id
  api_service_account_email = module.iam.api_service_account_email
  labels                    = local.common_labels
}

module "memorystore" {
  source = "./modules/memorystore"

  name_prefix         = local.name_prefix
  region              = var.region
  redis_tier          = var.redis_tier
  redis_memory_size_gb = var.redis_memory_size_gb
  network_id          = module.networking.network_self_link
  labels              = local.common_labels
}

module "cloud-storage" {
  source = "./modules/cloud-storage"

  name_prefix = local.name_prefix
  location    = var.region
  labels      = local.common_labels
}

module "secret-manager" {
  source = "./modules/secret-manager"

  name_prefix = local.name_prefix
  labels      = local.common_labels
}

module "iam" {
  source = "./modules/iam"

  name_prefix              = local.name_prefix
  project_id               = var.project_id
  cloud_sql_connection_name = module.cloud-sql.connection_name
  gcs_bucket_name          = module.cloud-storage.bucket_name
}

# Cloud Run is deployed via CI/CD pipeline after Docker images are built
# module "cloud-run" { ... }

module "gke" {
  source = "./modules/gke"

  name_prefix   = local.name_prefix
  region        = var.region
  project_id    = var.project_id
  machine_type  = var.gke_machine_type
  min_nodes     = var.gke_min_nodes
  max_nodes     = var.gke_max_nodes
  network_id    = module.networking.network_self_link
  worker_service_account_email = module.iam.worker_service_account_email
  labels        = local.common_labels
}

module "monitoring" {
  source = "./modules/monitoring"

  name_prefix        = local.name_prefix
  project_id         = var.project_id
  notification_email = var.notification_email
  labels             = local.common_labels
}
