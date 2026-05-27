variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "db_tier" {
  description = "Cloud SQL machine tier"
  type        = string
  default     = "db-f1-micro"
}

variable "db_disk_size_gb" {
  description = "Cloud SQL disk size in GB"
  type        = number
  default     = 20
}

variable "redis_tier" {
  description = "Memorystore Redis tier (BASIC, STANDARD_HA)"
  type        = string
  default     = "BASIC"
}

variable "redis_memory_size_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}

variable "gke_machine_type" {
  description = "GKE node machine type"
  type        = string
  default     = "e2-custom-2-4096"
}

variable "gke_min_nodes" {
  description = "Minimum GKE nodes"
  type        = number
  default     = 1
}

variable "gke_max_nodes" {
  description = "Maximum GKE nodes"
  type        = number
  default     = 3
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

variable "budget_amount" {
  description = "Monthly budget amount in EUR"
  type        = number
  default     = 200
}

variable "notification_email" {
  description = "Email for budget and monitoring alerts"
  type        = string
}

variable "billing_account_id" {
  description = "GCP billing account ID"
  type        = string
}

variable "domain" {
  description = "Custom domain (leave empty to skip Cloud DNS)"
  type        = string
  default     = ""
}

variable "cors_origins" {
  description = "Comma-separated frontend origins allowed to call the API"
  type        = string
  default     = ""
}
