# ===========================================================================
# Required
# ===========================================================================
variable "name_prefix" {
  description = "Prefix for ECS resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "Security group ID for ECS tasks (created in root to break circular deps)"
  type        = string
}

variable "aws_region" {
  description = "AWS region name for CloudWatch log configuration"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

# ===========================================================================
# Container Images
# ===========================================================================
variable "api_image" {
  description = "Full ECR image URI for API"
  type        = string
}

variable "frontend_image" {
  description = "Full ECR image URI for frontend"
  type        = string
}

variable "worker_image" {
  description = "Full ECR image URI for worker"
  type        = string
}

# ===========================================================================
# Resource Allocation
# ===========================================================================
variable "api_cpu" {
  description = "CPU units for API task (256 = 0.25 vCPU)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Memory for API task (MiB)"
  type        = number
  default     = 1024
}

variable "frontend_cpu" {
  description = "CPU units for frontend task"
  type        = number
  default     = 512
}

variable "frontend_memory" {
  description = "Memory for frontend task (MiB)"
  type        = number
  default     = 1024
}

variable "worker_cpu" {
  description = "CPU units for worker task"
  type        = number
  default     = 512
}

variable "worker_memory" {
  description = "Memory for worker task (MiB)"
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Desired task count for API service"
  type        = number
  default     = 1
}

variable "frontend_desired_count" {
  description = "Desired task count for frontend service"
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Desired task count for worker service (0 = disabled)"
  type        = number
  default     = 0
}

variable "worker_enabled" {
  description = "Enable worker at API runtime level (WORKER_ENABLED env var)"
  type        = string
  default     = "false"
}

# ===========================================================================
# Infrastructure References
# ===========================================================================
variable "redis_enabled" {
  description = "Whether Redis is available"
  type        = bool
  default     = true
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
}

variable "database_url" {
  description = "PostgreSQL connection URL (with password)"
  type        = string
  sensitive   = true
}

variable "artifacts_bucket_name" {
  description = "S3 bucket name for artifacts"
  type        = string
}

variable "artifacts_bucket_arn" {
  description = "S3 bucket ARN for artifacts"
  type        = string
}

variable "secret_arns" {
  description = "List of Secrets Manager ARNs the tasks need access to"
  type        = list(string)
  default     = []
}

variable "api_log_group_name" {
  description = "CloudWatch log group name for API"
  type        = string
}

variable "frontend_log_group_name" {
  description = "CloudWatch log group name for frontend"
  type        = string
}

variable "worker_log_group_name" {
  description = "CloudWatch log group name for worker"
  type        = string
}

# ===========================================================================
# Application Config
# ===========================================================================
variable "cors_origins" {
  description = "CORS allowed origins"
  type        = string
  default     = ""
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "llm_provider" {
  description = "LLM provider selection"
  type        = string
  default     = "deepseek"
}

variable "resend_from_email" {
  description = "Sender email for Resend"
  type        = string
  default     = "onboarding@resend.dev"
}

# ===========================================================================
# Secret ARNs (for secrets from Secrets Manager)
# ===========================================================================
variable "jwt_secret_arn" {
  description = "ARN of JWT secret key in Secrets Manager"
  type        = string
  default     = ""
}

variable "deepseek_api_key_arn" {
  description = "ARN of DeepSeek API key secret"
  type        = string
  default     = ""
}

variable "resend_api_key_arn" {
  description = "ARN of Resend API key secret"
  type        = string
  default     = ""
}

# ===========================================================================
# GitHub OIDC
# ===========================================================================
variable "github_repo" {
  description = "GitHub repository in owner/repo format for OIDC trust"
  type        = string
  default     = "BladeRunnerYao/dachjob.ai"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
