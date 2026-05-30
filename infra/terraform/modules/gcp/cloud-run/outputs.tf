output "api_url" {
  description = "URL of the deployed API service"
  value       = google_cloud_run_v2_service.api.uri
}

output "frontend_url" {
  description = "URL of the deployed frontend service"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "api_service_name" {
  description = "Name of the API Cloud Run service"
  value       = google_cloud_run_v2_service.api.name
}

output "frontend_service_name" {
  description = "Name of the frontend Cloud Run service"
  value       = google_cloud_run_v2_service.frontend.name
}
