resource "azurerm_container_registry" "this" {
  name                = replace("${var.name_prefix}acr", "/[^a-zA-Z0-9]/", "")
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = true
  tags                = var.tags
}
