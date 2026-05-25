resource "azurerm_storage_account" "this" {
  name                     = replace("${var.name_prefix}storage", "/[^a-zA-Z0-9]/", "")
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = var.tags
}

resource "azurerm_storage_container" "artifacts" {
  name                  = "${var.name_prefix}-artifacts"
  storage_account_name  = azurerm_storage_account.this.name
  container_access_type = "private"
}
