variable "name_prefix" {
  description = "Prefix for ElastiCache resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "IDs of private subnets for ElastiCache"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "Security group ID for ECS tasks (allowed to connect to Redis)"
  type        = string
}

variable "node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "num_cache_nodes" {
  description = "Number of cache nodes (1 for dev)"
  type        = number
  default     = 1
}

variable "parameter_group_name" {
  description = "Redis parameter group name"
  type        = string
  default     = "default.redis7"
}

variable "engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.1"
}

variable "transit_encryption_enabled" {
  description = "Enable in-transit encryption (disabled for dev matching GCP pattern)"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
