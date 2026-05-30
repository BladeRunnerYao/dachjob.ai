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

  name_prefix                  = var.name_prefix
  resource_group_name          = module.networking.resource_group_name
  location                     = var.location
  administrator_password       = var.postgres_administrator_password
  postgres_subnet_id           = module.networking.postgres_subnet_id
  postgres_private_dns_zone_id = module.networking.postgres_private_dns_zone_id
  tags                         = var.tags

  depends_on = [module.networking]
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
  secrets = merge(
    {
      "postgres-administrator-password" = var.postgres_administrator_password
    },
    nonsensitive(var.azure_openai_api_key != "") ? {
      "azure-openai-api-key" = var.azure_openai_api_key
    } : {},
    nonsensitive(var.deepseek_api_key != "") ? {
      "deepseek-api-key" = var.deepseek_api_key
    } : {},
    nonsensitive(var.jwt_secret != "") ? {
      "jwt-secret" = var.jwt_secret
    } : {},
    nonsensitive(var.secret_key != "") ? {
      "secret-key" = var.secret_key
    } : {},
    nonsensitive(var.resend_api_key != "") ? {
      "resend-api-key" = var.resend_api_key
    } : {},
  )
  tags = var.tags
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
  redis_enabled                   = var.redis_enabled
  storage_account_name            = module.storage.storage_account_name
  storage_container_name          = module.storage.storage_container_name
  storage_connection_string       = module.storage.primary_connection_string
  cors_origins                    = var.cors_origins
  azure_openai_api_key            = var.azure_openai_api_key
  azure_openai_endpoint           = var.azure_openai_endpoint
  azure_openai_api_version        = var.azure_openai_api_version
  azure_openai_model_fast         = var.azure_openai_model_fast
  azure_openai_model_quality      = var.azure_openai_model_quality
  azure_openai_model_reasoning    = var.azure_openai_model_reasoning
  deepseek_api_key                = var.deepseek_api_key
  jwt_secret                      = var.jwt_secret
  secret_key                      = var.secret_key
  resend_api_key                  = var.resend_api_key
  resend_from_email               = var.resend_from_email
  tags                            = var.tags
}
