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

variable "tags" {
  type    = map(string)
  default = {}
}
