variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "redis_tier" {
  type = string
}

variable "redis_memory_size_gb" {
  type = number
}

variable "network_id" {
  type = string
}

variable "labels" {
  type    = map(string)
  default = {}
}
