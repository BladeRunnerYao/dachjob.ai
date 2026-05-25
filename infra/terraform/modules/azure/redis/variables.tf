variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "capacity" {
  description = "Redis cache capacity (1=Basic/Standard, 2=Standard, etc.)"
  type        = number
  default     = 1
}

variable "family" {
  description = "Redis SKU family (C=Basic/Standard, P=Premium)"
  type        = string
  default     = "C"
}

variable "sku_name" {
  description = "Redis SKU (Basic, Standard, Premium)"
  type        = string
  default     = "Basic"
}

variable "tags" {
  type    = map(string)
  default = {}
}
