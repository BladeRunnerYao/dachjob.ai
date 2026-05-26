module "networking" {
  source = "../../../modules/azure/networking"

  name_prefix = var.name_prefix
  location    = var.location
  tags        = var.tags
}

module "monitoring" {
  source = "../../../modules/azure/monitoring"

  name_prefix         = var.name_prefix
  resource_group_name = module.networking.resource_group_name
  location            = module.networking.location
  tags                = var.tags
}

module "container_registry" {
  source = "../../../modules/azure/container-registry"

  name_prefix         = var.name_prefix
  resource_group_name = module.networking.resource_group_name
  location            = module.networking.location
  tags                = var.tags
}

module "postgres" {
  source = "../../../modules/azure/postgres"

  name_prefix            = var.name_prefix
  resource_group_name    = module.networking.resource_group_name
  location               = var.location
  administrator_password = var.postgres_administrator_password
  tags                   = var.tags
}

module "redis" {
  source = "../../../modules/azure/redis"

  name_prefix         = var.name_prefix
  resource_group_name = module.networking.resource_group_name
  location            = module.networking.location
  tags                = var.tags
}

module "storage" {
  source = "../../../modules/azure/storage"

  name_prefix         = var.name_prefix
  resource_group_name = module.networking.resource_group_name
  location            = module.networking.location
  tags                = var.tags
}

module "key_vault" {
  source = "../../../modules/azure/key-vault"

  name_prefix         = var.name_prefix
  resource_group_name = module.networking.resource_group_name
  location            = module.networking.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  tags                = var.tags
}

data "azurerm_client_config" "current" {}

module "container_apps" {
  source = "../../../modules/azure/container-apps"

  name_prefix                     = var.name_prefix
  resource_group_name             = module.networking.resource_group_name
  location                        = module.networking.location
  container_apps_subnet_id        = module.networking.container_apps_subnet_id
  log_analytics_workspace_id      = module.monitoring.log_analytics_workspace_id
  acr_login_server                = module.container_registry.acr_login_server
  acr_name                        = module.container_registry.acr_name
  subscription_id                 = data.azurerm_client_config.current.subscription_id
  api_image                       = "${module.container_registry.acr_login_server}/api:${var.api_image_tag}"
  frontend_image                  = "${module.container_registry.acr_login_server}/frontend:${var.frontend_image_tag}"
  worker_image                    = "${module.container_registry.acr_login_server}/worker:${var.worker_image_tag}"
  postgres_host                   = module.postgres.postgres_host
  postgres_administrator_login    = module.postgres.administrator_login
  postgres_administrator_password = var.postgres_administrator_password
  redis_hostname                  = module.redis.redis_hostname
  redis_primary_key               = module.redis.redis_primary_key
  storage_account_name            = module.storage.storage_account_name
  storage_container_name          = module.storage.storage_container_name
  storage_connection_string       = module.storage.primary_connection_string
  cors_origins                    = var.cors_origins
  tags                            = var.tags
}
