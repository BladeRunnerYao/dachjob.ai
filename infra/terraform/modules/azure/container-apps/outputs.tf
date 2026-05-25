output "api_url" {
  description = "URL of the deployed API container app"
  value       = "https://${azurerm_container_app.api.ingress[0].fqdn}"
}

output "frontend_url" {
  description = "URL of the deployed frontend container app"
  value       = "https://${azurerm_container_app.frontend.ingress[0].fqdn}"
}

output "container_app_environment_name" {
  description = "Container Apps Environment name"
  value       = azurerm_container_app_environment.this.name
}

output "managed_identity_id" {
  description = "User-assigned managed identity ID"
  value       = azurerm_user_assigned_identity.this.id
}

output "managed_identity_client_id" {
  description = "User-assigned managed identity client ID"
  value       = azurerm_user_assigned_identity.this.client_id
}
