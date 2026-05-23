output "api_service_account_email" {
  description = "API service account email"
  value       = google_service_account.api.email
}

output "frontend_service_account_email" {
  description = "Frontend service account email"
  value       = google_service_account.frontend.email
}

output "worker_service_account_email" {
  description = "Worker service account email"
  value       = google_service_account.worker.email
}

output "terraform_service_account_email" {
  description = "Terraform CI service account email"
  value       = google_service_account.terraform.email
}

output "service_accounts" {
  description = "Map of all service account emails"
  value = {
    api       = google_service_account.api.email
    frontend  = google_service_account.frontend.email
    worker    = google_service_account.worker.email
    terraform = google_service_account.terraform.email
  }
}
