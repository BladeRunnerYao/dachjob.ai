variable "name_prefix" {
  description = "Prefix for all Azure resource names"
  type        = string
  default     = "dachjob-dev"
}

variable "location" {
  description = "Azure region for most resources"
  type        = string
  default     = "westeurope"
}

variable "postgres_location" {
  description = "Azure region for PostgreSQL (some free subscriptions restrict westeurope)"
  type        = string
  default     = "westeurope"
}

variable "postgres_administrator_password" {
  description = "Password for PostgreSQL administrator"
  type        = string
  sensitive   = true
}

variable "api_image_tag" {
  description = "Docker image tag for the API"
  type        = string
  default     = "latest"
}

variable "frontend_image_tag" {
  description = "Docker image tag for the frontend"
  type        = string
  default     = "latest"
}

variable "worker_image_tag" {
  description = "Docker image tag for the Celery worker"
  type        = string
  default     = "latest"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    environment = "dev"
    managed_by  = "terraform"
    project     = "dachjob"
  }
}
