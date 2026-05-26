resource "azurerm_user_assigned_identity" "this" {
  name                = "${var.name_prefix}-ca-identity"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = "/subscriptions/${var.subscription_id}/resourceGroups/${var.resource_group_name}/providers/Microsoft.ContainerRegistry/registries/${var.acr_name}"
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}

resource "azurerm_container_app_environment" "this" {
  name                       = "${var.name_prefix}-cae"
  resource_group_name        = var.resource_group_name
  location                   = var.location
  log_analytics_workspace_id = var.log_analytics_workspace_id
  infrastructure_subnet_id   = var.container_apps_subnet_id
  tags                       = var.tags
}

resource "azurerm_container_app" "api" {
  name                         = "${var.name_prefix}-api"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  template {
    max_replicas = 10

    container {
      name   = "api"
      image  = var.api_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "DATABASE_URL"
        value = "postgresql+asyncpg://${var.postgres_administrator_login}:${var.postgres_administrator_password}@${var.postgres_host}:5432/dachjob"
      }
      env {
        name  = "REDIS_URL"
        value = "rediss://:${var.redis_primary_key}@${var.redis_hostname}:6380/0"
      }
      env {
        name  = "REDIS_ENABLED"
        value = "true"
      }
      env {
        name  = "STORAGE_PROVIDER"
        value = "azure_blob"
      }
      env {
        name  = "STORAGE_BUCKET_NAME"
        value = var.storage_container_name
      }
      env {
        name  = "AZURE_STORAGE_CONNECTION_STRING"
        value = var.storage_connection_string
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER_NAME"
        value = var.storage_container_name
      }
      env {
        name  = "LLM_PROVIDER"
        value = "azure_openai"
      }
              env {
                  name  = "CORS_ORIGINS"
                  value = var.cors_origins != "" ? var.cors_origins : "https://${var.name_prefix}-frontend.--placeholder--"
                }

      liveness_probe {
        port    = 8000
        transport = "HTTP"
        path      = "/api/health"
      }

      readiness_probe {
        port      = 8000
        transport = "HTTP"
        path      = "/api/health"
      }
    }
  }

  registry {
    server   = var.acr_login_server
    identity = azurerm_user_assigned_identity.this.id
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 8000
    transport                  = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  identity {
    type = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }
}

resource "azurerm_container_app" "frontend" {
  name                         = "${var.name_prefix}-frontend"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  template {
    max_replicas = 10

    container {
      name   = "frontend"
      image  = var.frontend_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "NEXT_PUBLIC_API_BASE_URL"
        value = "https://${azurerm_container_app.api.ingress[0].fqdn}"
      }
      env {
        name  = "NODE_ENV"
        value = "production"
      }

      liveness_probe {
        port      = 3000
        transport = "HTTP"
        path      = "/"
      }
    }
  }

  registry {
    server   = var.acr_login_server
    identity = azurerm_user_assigned_identity.this.id
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = 3000
    transport                  = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  identity {
    type = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }
}

resource "azurerm_container_app" "worker" {
  name                         = "${var.name_prefix}-worker"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  template {
    max_replicas = 3
    min_replicas = 1

    container {
      name   = "worker"
      image  = var.worker_image
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "DATABASE_URL"
        value = "postgresql+asyncpg://${var.postgres_administrator_login}:${var.postgres_administrator_password}@${var.postgres_host}:5432/dachjob"
      }
      env {
        name  = "REDIS_URL"
        value = "rediss://:${var.redis_primary_key}@${var.redis_hostname}:6380/0"
      }
      env {
        name  = "REDIS_ENABLED"
        value = "true"
      }
      env {
        name  = "STORAGE_PROVIDER"
        value = "azure_blob"
      }
      env {
        name  = "STORAGE_BUCKET_NAME"
        value = var.storage_container_name
      }
      env {
        name  = "AZURE_STORAGE_CONNECTION_STRING"
        value = var.storage_connection_string
      }
      env {
        name  = "AZURE_STORAGE_CONTAINER_NAME"
        value = var.storage_container_name
      }
      env {
        name  = "LLM_PROVIDER"
        value = "azure_openai"
      }
    }
  }

  registry {
    server   = var.acr_login_server
    identity = azurerm_user_assigned_identity.this.id
  }

  identity {
    type = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }
}
