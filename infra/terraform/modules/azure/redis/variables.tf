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
  type        = number
  default     = 1
}

variable "family" {
  type        = string
  default     = "C"
}

variable "sku_name" {
  type        = string
  default     = "Basic"
}

variable "tags" {
  type    = map(string)
  default = {}
}
