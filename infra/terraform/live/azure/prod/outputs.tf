output "api_url" {
  description = "API Container App URL"
  value       = module.container_apps.api_url
}

output "frontend_url" {
  description = "Frontend Container App URL"
  value       = module.container_apps.frontend_url
}

output "acr_login_server" {
  description = "ACR login server for docker push"
  value       = module.container_registry.acr_login_server
}

output "resource_group_name" {
  description = "Azure resource group name"
  value       = module.networking.resource_group_name
}

output "container_app_environment_name" {
  description = "Container Apps Environment name"
  value       = module.container_apps.container_app_environment_name
}

output "postgres_host" {
  description = "PostgreSQL server FQDN"
  value       = module.postgres.postgres_host
}

output "redis_hostname" {
  description = "Redis hostname"
  value       = module.redis.redis_hostname
}

output "storage_account_name" {
  description = "Storage account name"
  value       = module.storage.storage_account_name
}

output "storage_container_name" {
  description = "Blob container name for artifacts"
  value       = module.storage.storage_container_name
}

output "key_vault_name" {
  description = "Key Vault name"
  value       = module.key_vault.key_vault_name
}
