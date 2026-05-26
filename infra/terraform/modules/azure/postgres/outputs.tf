output "postgres_host" {
  description = "PostgreSQL server FQDN"
  value       = azurerm_postgresql_flexible_server.this.fqdn
}

output "postgres_server_id" {
  description = "PostgreSQL server resource ID"
  value       = azurerm_postgresql_flexible_server.this.id
}

output "database_name" {
  description = "Database name"
  value       = azurerm_postgresql_flexible_server_database.this.name
}

output "administrator_login" {
  description = "PostgreSQL administrator login"
  value       = azurerm_postgresql_flexible_server.this.administrator_login
}
