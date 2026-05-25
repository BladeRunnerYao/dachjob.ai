resource "random_id" "pg_suffix" {
  byte_length = 3
}

resource "azurerm_postgresql_flexible_server" "this" {
  name                         = "${var.name_prefix}-pg-${random_id.pg_suffix.hex}"
  resource_group_name          = var.resource_group_name
  location                     = var.location
  version                      = var.postgres_version
  delegated_subnet_id          = var.subnet_id
  private_dns_zone_id          = var.private_dns_zone_id
  administrator_login          = var.administrator_login
  administrator_password       = var.administrator_password
  sku_name                     = var.sku_name
  storage_mb                   = var.storage_mb
  backup_retention_days        = 7
  geo_redundant_backup_enabled = false
  auto_grow_enabled            = true
  public_network_access_enabled = false

  lifecycle {
    ignore_changes = [
      zone,
      high_availability,
    ]
  }

  tags = var.tags
}

resource "azurerm_postgresql_flexible_server_database" "this" {
  name      = "dachjob"
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
}

resource "azurerm_postgresql_flexible_server_configuration" "pgvector" {
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.this.id
  value     = "vector"
}
