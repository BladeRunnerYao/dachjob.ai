variable "name_prefix" {
  description = "Prefix for RDS resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "IDs of private subnets for RDS"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "Security group ID for ECS tasks (allowed to connect to RDS)"
  type        = string
}

variable "engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16.14"
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Maximum allocated storage with autoscaling (GB)"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "dachjob"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "dachjob_admin"
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on destroy (set true for dev)"
  type        = bool
  default     = true
}

variable "backup_retention_period" {
  description = "Backup retention in days (1 for free tier, max 35)"
  type        = number
  default     = 1
}

variable "iam_db_auth" {
  description = "Enable IAM database authentication"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
