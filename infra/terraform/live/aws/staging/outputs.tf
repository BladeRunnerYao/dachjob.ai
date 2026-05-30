output "api_url" {
  description = "API base URL (via ALB)"
  value       = module.ecs.api_url
}

output "frontend_url" {
  description = "Frontend URL (CloudFront if configured, otherwise ALB)"
  value       = module.ecs.frontend_url
}

output "alb_frontend_url" {
  description = "Frontend URL via ALB directly"
  value       = module.ecs.alb_frontend_url
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = module.ecs.alb_dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.ecs.cluster_name
}

output "api_service_name" {
  description = "ECS API service name"
  value       = module.ecs.api_service_name
}

output "frontend_service_name" {
  description = "ECS frontend service name"
  value       = module.ecs.frontend_service_name
}

output "worker_service_name" {
  description = "ECS worker service name"
  value       = module.ecs.worker_service_name
}

output "rds_endpoint" {
  description = "RDS endpoint (host:port)"
  value       = module.rds.endpoint
}

output "redis_endpoint" {
  description = "Redis endpoint (host:port)"
  value       = module.elasticache.endpoint
}

output "artifacts_bucket" {
  description = "S3 artifacts bucket name"
  value       = module.s3.artifacts_bucket_name
}

output "ecr_api_repo_url" {
  description = "ECR API repo URL"
  value       = module.ecr.api_repo_url
}

output "github_actions_role_arn" {
  description = "GitHub Actions OIDC role ARN"
  value       = module.ecs.github_actions_role_arn
}
