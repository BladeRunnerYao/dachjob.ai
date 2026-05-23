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

variable "vpc_connector_id" {
  type = string
}

variable "network_id" {
  description = "VPC network self-link for private networking"
  type        = string
}

variable "labels" {
  type    = map(string)
  default = {}
}
