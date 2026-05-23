output "bucket_name" {
  description = "Name of the main artifacts GCS bucket"
  value       = google_storage_bucket.artifacts.name
}

output "static_bucket_name" {
  description = "Name of the static assets GCS bucket"
  value       = google_storage_bucket.static_assets.name
}

# output "terraform_state_bucket" {
#   description = "Name of the Terraform state GCS bucket"
#   value       = google_storage_bucket.terraform_state.name
# }
