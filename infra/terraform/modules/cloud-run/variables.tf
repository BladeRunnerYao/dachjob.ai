variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "project_id" {
  type = string
}

variable "vpc_connector_id" {
  type = string
}

variable "api_image" {
  type = string
}

variable "frontend_image" {
  type = string
}

variable "cloud_sql_connection_name" {
  type = string
}

variable "redis_host" {
  type = string
}

variable "gcs_bucket_name" {
  type = string
}

variable "api_service_account_email" {
  type = string
}

variable "frontend_service_account_email" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}
