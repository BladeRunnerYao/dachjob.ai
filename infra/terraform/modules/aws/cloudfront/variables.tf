variable "name_prefix" {
  description = "Prefix for CloudFront resource names"
  type        = string
}

variable "alb_dns_name" {
  description = "ALB DNS name to use as CloudFront origin"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
