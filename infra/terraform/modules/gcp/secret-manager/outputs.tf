output "secret_ids" {
  description = "Map of secret names to their IDs"
  value = {
    openrouter_api_key     = google_secret_manager_secret.openrouter_api_key.id
    deepseek_api_key       = google_secret_manager_secret.deepseek_api_key.id
    jwt_secret_key         = google_secret_manager_secret.jwt_secret_key.id
    google_oauth_client_id = google_secret_manager_secret.google_oauth_client_id.id
    db_password            = google_secret_manager_secret.db_password.id
  }
}
