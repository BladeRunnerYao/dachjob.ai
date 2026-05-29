output "api_log_group_name" {
  description = "API CloudWatch log group name"
  value       = aws_cloudwatch_log_group.api.name
}

output "frontend_log_group_name" {
  description = "Frontend CloudWatch log group name"
  value       = aws_cloudwatch_log_group.frontend.name
}

output "worker_log_group_name" {
  description = "Worker CloudWatch log group name"
  value       = aws_cloudwatch_log_group.worker.name
}

output "alarm_topic_arn" {
  description = "SNS alarm topic ARN"
  value       = aws_sns_topic.alarms.arn
}
