output "api_repo_url" {
  description = "ECR repository URL for API"
  value       = aws_ecr_repository.api.repository_url
}

output "frontend_repo_url" {
  description = "ECR repository URL for frontend"
  value       = aws_ecr_repository.frontend.repository_url
}

output "worker_repo_url" {
  description = "ECR repository URL for worker"
  value       = aws_ecr_repository.worker.repository_url
}

output "api_repo_name" {
  description = "ECR repository name for API"
  value       = aws_ecr_repository.api.name
}

output "frontend_repo_name" {
  description = "ECR repository name for frontend"
  value       = aws_ecr_repository.frontend.name
}

output "worker_repo_name" {
  description = "ECR repository name for worker"
  value       = aws_ecr_repository.worker.name
}
