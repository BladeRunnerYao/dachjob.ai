output "gke_cluster_name" {
  description = "Name of the GKE cluster"
  value       = module.gke.cluster_name
}

output "gke_cluster_endpoint" {
  description = "GKE cluster endpoint"
  value       = module.gke.endpoint
  sensitive   = true
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name for the backend"
  value       = module.cloud-sql.connection_name
}

output "redis_host" {
  description = "Redis host address"
  value       = module.memorystore.host
}

output "gcs_bucket_name" {
  description = "GCS bucket name for artifacts"
  value       = module.cloud-storage.bucket_name
}

output "artifact_registry_repositories" {
  description = "Artifact Registry repository names"
  value       = module.artifact-registry.repositories
}

output "service_accounts" {
  description = "Service account emails"
  value       = module.iam.service_accounts
}

output "cloud_run_urls" {
  description = "Cloud Run service URLs"
  value = {
    api      = module.cloud-run.api_url
    frontend = module.cloud-run.frontend_url
  }
}

output "api_url" {
  description = "Cloud Run API URL"
  value       = module.cloud-run.api_url
}

output "frontend_url" {
  description = "Cloud Run frontend URL"
  value       = module.cloud-run.frontend_url
}
