variable "name_prefix" {
  description = "Prefix for monitoring resource names"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix for CloudWatch alarm dimension"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
