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

locals {
  database_url                 = "postgresql+asyncpg://${var.postgres_administrator_login}:${var.postgres_administrator_password}@${var.postgres_host}:5432/dachjob"
  redis_url                    = "rediss://:${var.redis_primary_key}@${var.redis_hostname}:6380/0"
  has_azure_openai_api_key     = nonsensitive(var.azure_openai_api_key != "")
  has_jwt_secret               = nonsensitive(var.jwt_secret != "")
  has_secret_key               = nonsensitive(var.secret_key != "")
  has_resend_api_key           = nonsensitive(var.resend_api_key != "")
  azure_openai_api_key_secret  = "azure-openai-api-key"
  jwt_secret_name              = "jwt-secret"
  secret_key_name              = "secret-key"
  resend_api_key_secret        = "resend-api-key"
}

resource "azurerm_container_app" "api" {
  name                         = "${var.name_prefix}-api"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  secret {
    name  = "database-url"
    value = local.database_url
  }

  secret {
    name  = "redis-url"
    value = local.redis_url
  }

  secret {
    name  = "azure-storage-connection-string"
    value = var.storage_connection_string
  }

  dynamic "secret" {
    for_each = local.has_azure_openai_api_key ? [1] : []
    content {
      name  = local.azure_openai_api_key_secret
      value = var.azure_openai_api_key
    }
  }

  dynamic "secret" {
    for_each = local.has_jwt_secret ? [1] : []
    content {
      name  = local.jwt_secret_name
      value = var.jwt_secret
    }
  }

  dynamic "secret" {
    for_each = local.has_secret_key ? [1] : []
    content {
      name  = local.secret_key_name
      value = var.secret_key
    }
  }

  dynamic "secret" {
    for_each = local.has_resend_api_key ? [1] : []
    content {
      name  = local.resend_api_key_secret
      value = var.resend_api_key
    }
  }

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
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name  = "REDIS_ENABLED"
        value = tostring(var.redis_enabled)
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
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "azure-storage-connection-string"
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
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.azure_openai_endpoint
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = var.azure_openai_api_version
      }
      env {
        name  = "AZURE_OPENAI_MODEL_FAST"
        value = var.azure_openai_model_fast
      }
      env {
        name  = "AZURE_OPENAI_MODEL_QUALITY"
        value = var.azure_openai_model_quality
      }
      env {
        name  = "AZURE_OPENAI_MODEL_REASONING"
        value = var.azure_openai_model_reasoning
      }
      env {
        name  = "RESEND_FROM_EMAIL"
        value = var.resend_from_email
      }
      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins != "" ? var.cors_origins : "https://${var.name_prefix}-frontend.--placeholder--"
      }

      dynamic "env" {
        for_each = local.has_azure_openai_api_key ? [1] : []
        content {
          name        = "AZURE_OPENAI_API_KEY"
          secret_name = local.azure_openai_api_key_secret
        }
      }

      dynamic "env" {
        for_each = local.has_jwt_secret ? [1] : []
        content {
          name        = "JWT_SECRET"
          secret_name = local.jwt_secret_name
        }
      }

      dynamic "env" {
        for_each = local.has_secret_key ? [1] : []
        content {
          name        = "SECRET_KEY"
          secret_name = local.secret_key_name
        }
      }

      dynamic "env" {
        for_each = local.has_resend_api_key ? [1] : []
        content {
          name        = "RESEND_API_KEY"
          secret_name = local.resend_api_key_secret
        }
      }

      liveness_probe {
        port      = 8000
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
    type         = "UserAssigned"
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
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }
}

resource "azurerm_container_app" "worker" {
  name                         = "${var.name_prefix}-worker"
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  secret {
    name  = "database-url"
    value = local.database_url
  }

  secret {
    name  = "redis-url"
    value = local.redis_url
  }

  secret {
    name  = "azure-storage-connection-string"
    value = var.storage_connection_string
  }

  dynamic "secret" {
    for_each = local.has_azure_openai_api_key ? [1] : []
    content {
      name  = local.azure_openai_api_key_secret
      value = var.azure_openai_api_key
    }
  }

  dynamic "secret" {
    for_each = local.has_jwt_secret ? [1] : []
    content {
      name  = local.jwt_secret_name
      value = var.jwt_secret
    }
  }

  dynamic "secret" {
    for_each = local.has_secret_key ? [1] : []
    content {
      name  = local.secret_key_name
      value = var.secret_key
    }
  }

  dynamic "secret" {
    for_each = local.has_resend_api_key ? [1] : []
    content {
      name  = local.resend_api_key_secret
      value = var.resend_api_key
    }
  }

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
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name        = "REDIS_URL"
        secret_name = "redis-url"
      }
      env {
        name  = "REDIS_ENABLED"
        value = tostring(var.redis_enabled)
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
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "azure-storage-connection-string"
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
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.azure_openai_endpoint
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = var.azure_openai_api_version
      }
      env {
        name  = "AZURE_OPENAI_MODEL_FAST"
        value = var.azure_openai_model_fast
      }
      env {
        name  = "AZURE_OPENAI_MODEL_QUALITY"
        value = var.azure_openai_model_quality
      }
      env {
        name  = "AZURE_OPENAI_MODEL_REASONING"
        value = var.azure_openai_model_reasoning
      }
      env {
        name  = "RESEND_FROM_EMAIL"
        value = var.resend_from_email
      }

      dynamic "env" {
        for_each = local.has_azure_openai_api_key ? [1] : []
        content {
          name        = "AZURE_OPENAI_API_KEY"
          secret_name = local.azure_openai_api_key_secret
        }
      }

      dynamic "env" {
        for_each = local.has_jwt_secret ? [1] : []
        content {
          name        = "JWT_SECRET"
          secret_name = local.jwt_secret_name
        }
      }

      dynamic "env" {
        for_each = local.has_secret_key ? [1] : []
        content {
          name        = "SECRET_KEY"
          secret_name = local.secret_key_name
        }
      }

      dynamic "env" {
        for_each = local.has_resend_api_key ? [1] : []
        content {
          name        = "RESEND_API_KEY"
          secret_name = local.resend_api_key_secret
        }
      }
    }
  }

  registry {
    server   = var.acr_login_server
    identity = azurerm_user_assigned_identity.this.id
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }
}
