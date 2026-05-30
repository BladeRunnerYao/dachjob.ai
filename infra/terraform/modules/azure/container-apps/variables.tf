variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "container_apps_subnet_id" {
  type = string
}

variable "log_analytics_workspace_id" {
  type = string
}

variable "acr_login_server" {
  type = string
}

variable "acr_name" {
  type = string
}

variable "subscription_id" {
  type = string
}

variable "api_image" {
  type = string
}

variable "frontend_image" {
  type = string
}

variable "worker_image" {
  type = string
}

variable "postgres_host" {
  type = string
}

variable "postgres_administrator_login" {
  type = string
}

variable "postgres_administrator_password" {
  type      = string
  sensitive = true
}

variable "redis_hostname" {
  type = string
}

variable "redis_primary_key" {
  type      = string
  sensitive = true
}

variable "redis_enabled" {
  type    = bool
  default = false
}

variable "storage_account_name" {
  type = string
}

variable "storage_container_name" {
  type = string
}

variable "storage_connection_string" {
  type      = string
  sensitive = true
}

variable "cors_origins" {
  type    = string
  default = ""
}

variable "azure_openai_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "azure_openai_endpoint" {
  type    = string
  default = ""
}

variable "azure_openai_api_version" {
  type    = string
  default = "2024-10-21"
}

variable "azure_openai_model_fast" {
  type    = string
  default = "gpt-4o-mini"
}

variable "azure_openai_model_quality" {
  type    = string
  default = "gpt-4o"
}

variable "azure_openai_model_reasoning" {
  type    = string
  default = "o1-mini"
}

variable "deepseek_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "jwt_secret" {
  type      = string
  default   = ""
  sensitive = true
}

variable "secret_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "resend_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "resend_from_email" {
  type    = string
  default = "onboarding@resend.dev"
}

variable "tags" {
  type    = map(string)
  default = {}
}
