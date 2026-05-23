variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "project_id" {
  type = string
}

variable "machine_type" {
  type = string
}

variable "min_nodes" {
  type = number
}

variable "max_nodes" {
  type = number
}

variable "network_id" {
  type = string
}

variable "worker_service_account_email" {
  type = string
}

variable "register_to_fleet" {
  description = "Register cluster to GKE Fleet (for Cloud Deploy / multi-cluster)"
  type        = bool
  default     = false
}

variable "labels" {
  type    = map(string)
  default = {}
}
