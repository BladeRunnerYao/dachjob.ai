variable "name_prefix" {
  description = "Prefix for S3 bucket names"
  type        = string
}

variable "lifecycle_days" {
  description = "Days before non-current object versions expire"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
