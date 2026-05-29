output "db_password_secret_arn" {
  description = "ARN of the DB password secret"
  value       = aws_secretsmanager_secret.db_password.arn
}

output "db_password_value" {
  description = "The generated DB password value"
  value       = random_password.db_password.result
  sensitive   = true
}

output "app_secret_arns" {
  description = "Map of secret name → ARN"
  value = {
    for k, v in aws_secretsmanager_secret.app : k => v.arn
  }
}

output "db_password_secret_name" {
  description = "Name of the DB password secret"
  value       = aws_secretsmanager_secret.db_password.name
}
