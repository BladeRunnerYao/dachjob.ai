variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "administrator_login" {
  type    = string
  default = "dachjob_admin"
}

variable "administrator_password" {
  type      = string
  sensitive = true
}

variable "postgres_version" {
  type    = string
  default = "16"
}

variable "sku_name" {
  type    = string
  default = "B_Standard_B1ms"
}

variable "storage_mb" {
  type    = number
  default = 32768
}

variable "postgres_subnet_id" {
  type        = string
  description = "ID of the delegated subnet used for PostgreSQL Flexible Server private access."
}

variable "postgres_private_dns_zone_id" {
  type        = string
  description = "ID of the private DNS zone linked to the PostgreSQL virtual network."
}

variable "tags" {
  type    = map(string)
  default = {}
}
