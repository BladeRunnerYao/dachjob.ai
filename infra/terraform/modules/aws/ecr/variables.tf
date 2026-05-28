variable "name_prefix" {
  description = "Prefix for ECR repository names"
  type        = string
}

variable "force_delete" {
  description = "Allow terraform destroy to delete non-empty repos"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
