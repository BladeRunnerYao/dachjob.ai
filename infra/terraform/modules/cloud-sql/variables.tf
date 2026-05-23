variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "db_tier" {
  type = string
}

variable "db_disk_size_gb" {
  type = number
}

variable "network_id" {
  description = "VPC network self-link for private networking"
  type        = string
}

variable "api_service_account_email" {
  description = "API service account email for IAM auth"
  type        = string
}

variable "labels" {
  type    = map(string)
  default = {}
}
