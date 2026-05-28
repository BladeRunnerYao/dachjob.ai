# ------------------------------------------------------------------------------
# AWS Dev Environment – Root Module
# ------------------------------------------------------------------------------
# Mirrors: infra/terraform/live/azure/dev/main.tf
#
# Region: eu-west-1 (Ireland) — closest to GCP europe-west1 / Azure westeurope

locals {
  region   = var.region
  az_count = 2
  secret_arns = concat(
    [module.secrets_manager.db_password_secret_arn],
    values(module.secrets_manager.app_secret_arns),
  )
  database_url = "postgresql+asyncpg://${module.rds.db_username}:${var.db_password}@${module.rds.address}:${module.rds.port}/${module.rds.db_name}"
}

# ===========================================================================
# Shared Security Group for ECS Tasks
# ===========================================================================
# Created here (not inside any module) to avoid circular dependencies:
# ECS → needs database_url (from RDS) and redis_url (from ElastiCache)
# RDS/ElastiCache → need ecs_security_group_id (from ECS)
# By creating the SG here, all modules can reference it without cycles.
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.name_prefix}-ecs-tasks-sg"
  description = "Security group for ECS tasks (shared)"
  vpc_id      = module.networking.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

# ===========================================================================
# Networking
# ===========================================================================
module "networking" {
  source = "../../../modules/aws/networking"

  name_prefix = var.name_prefix
  region      = var.region
  vpc_cidr    = "10.1.0.0/16"
  az_count    = local.az_count
  tags        = var.tags
}

# ===========================================================================
# ECR
# ===========================================================================
module "ecr" {
  source = "../../../modules/aws/ecr"

  name_prefix = var.name_prefix
  tags        = var.tags
}

# ===========================================================================
# RDS (PostgreSQL 16 + pgvector)
# ===========================================================================
module "rds" {
  source = "../../../modules/aws/rds"

  name_prefix           = var.name_prefix
  vpc_id                = module.networking.vpc_id
  private_subnet_ids    = module.networking.private_subnet_ids
  ecs_security_group_id = aws_security_group.ecs_tasks.id
  db_password           = var.db_password
  tags                  = var.tags
}

# ===========================================================================
# ElastiCache (Redis 7)
# ===========================================================================
module "elasticache" {
  source = "../../../modules/aws/elasticache"

  name_prefix           = var.name_prefix
  vpc_id                = module.networking.vpc_id
  private_subnet_ids    = module.networking.private_subnet_ids
  ecs_security_group_id = aws_security_group.ecs_tasks.id
  tags                  = var.tags
}

# ===========================================================================
# S3 (Artifact Storage)
# ===========================================================================
module "s3" {
  source = "../../../modules/aws/s3"

  name_prefix = var.name_prefix
  tags        = var.tags
}

# ===========================================================================
# Secrets Manager
# ===========================================================================
module "secrets_manager" {
  source = "../../../modules/aws/secrets-manager"

  name_prefix = var.name_prefix
  tags        = var.tags
}

# ===========================================================================
# ECS (Fargate Cluster + ALB + 3 Services)
# ===========================================================================
module "ecs" {
  source = "../../../modules/aws/ecs"

  name_prefix = var.name_prefix
  aws_region  = var.region
  vpc_id      = module.networking.vpc_id
  environment = var.environment
  github_repo = var.github_repo

  # Subnets
  public_subnet_ids  = module.networking.public_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids

  # ECS task security group (created in root to break circular dependency)
  ecs_security_group_id = aws_security_group.ecs_tasks.id

  # Container images
  api_image      = "${module.ecr.api_repo_url}:${var.api_image_tag}"
  frontend_image = "${module.ecr.frontend_repo_url}:${var.frontend_image_tag}"
  worker_image   = "${module.ecr.worker_repo_url}:${var.worker_image_tag}"

  # Resource allocation
  api_cpu                = var.api_cpu
  api_memory             = var.api_memory
  frontend_cpu           = var.frontend_cpu
  frontend_memory        = var.frontend_memory
  worker_cpu             = var.worker_cpu
  worker_memory          = var.worker_memory
  api_desired_count      = var.api_desired_count
  frontend_desired_count = var.frontend_desired_count
  worker_desired_count   = var.worker_desired_count
  worker_enabled         = var.worker_enabled

  # Infrastructure
  redis_enabled = var.redis_enabled
  redis_url     = module.elasticache.redis_url
  database_url  = local.database_url
  secret_arns   = local.secret_arns

  # S3
  artifacts_bucket_name = module.s3.artifacts_bucket_name
  artifacts_bucket_arn  = module.s3.artifacts_bucket_arn

  # Logging
  api_log_group_name      = module.monitoring.api_log_group_name
  frontend_log_group_name = module.monitoring.frontend_log_group_name
  worker_log_group_name   = module.monitoring.worker_log_group_name

  # Application config (allow ALB + local dev)
  cors_origins      = var.cors_origins != "" ? var.cors_origins : "http://${var.name_prefix}-alb-*.elb.amazonaws.com,http://localhost:3000"
  llm_provider      = var.llm_provider
  resend_from_email = var.resend_from_email

  # Secret ARNs for task definitions
  jwt_secret_arn       = module.secrets_manager.app_secret_arns["jwt-secret-key"]
  deepseek_api_key_arn = module.secrets_manager.app_secret_arns["deepseek-api-key"]
  resend_api_key_arn   = module.secrets_manager.app_secret_arns["smtp-password"]

  tags = var.tags
}

# ===========================================================================
# Monitoring (CloudWatch)
# ===========================================================================
module "monitoring" {
  source = "../../../modules/aws/monitoring"

  name_prefix    = var.name_prefix
  alb_arn_suffix = module.ecs.alb_arn_suffix
  tags           = var.tags
}
