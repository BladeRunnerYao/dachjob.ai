resource "azurerm_redis_cache" "this" {
  name                = "${var.name_prefix}-redis"
  resource_group_name = var.resource_group_name
  location            = var.location
  capacity            = var.capacity
  family              = var.family
  sku_name            = var.sku_name
  tags                = var.tags

  lifecycle {
    ignore_changes = [
      redis_configuration,
    ]
  }
}

resource "azurerm_redis_firewall_rule" "allow_azure" {
  name                = "${replace(var.name_prefix, "-", "_")}_allow_azure"
  redis_cache_name    = azurerm_redis_cache.this.name
  resource_group_name = var.resource_group_name
  start_ip            = "0.0.0.0"
  end_ip              = "0.0.0.0"
}
