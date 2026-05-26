variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "tenant_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "secrets" {
  description = "Map of secret names to values to store in Key Vault"
  type        = map(string)
  default     = {}
}
