output "resource_group_name" {
  description = "Name of the Azure resource group"
  value       = azurerm_resource_group.this.name
}

output "resource_group_id" {
  description = "ID of the Azure resource group"
  value       = azurerm_resource_group.this.id
}

output "location" {
  description = "Azure location"
  value       = azurerm_resource_group.this.location
}

output "vnet_id" {
  description = "ID of the virtual network"
  value       = azurerm_virtual_network.this.id
}

output "container_apps_subnet_id" {
  description = "ID of the Container Apps subnet"
  value       = azurerm_subnet.container_apps.id
}

output "postgres_subnet_id" {
  description = "ID of the PostgreSQL subnet"
  value       = azurerm_subnet.postgres.id
}

output "redis_subnet_id" {
  description = "ID of the Redis subnet"
  value       = azurerm_subnet.redis.id
}

output "postgres_private_dns_zone_id" {
  description = "ID of the PostgreSQL private DNS zone"
  value       = azurerm_private_dns_zone.postgres.id
}

output "redis_private_dns_zone_id" {
  description = "ID of the Redis private DNS zone"
  value       = azurerm_private_dns_zone.redis.id
}
