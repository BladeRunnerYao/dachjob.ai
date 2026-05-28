output "artifacts_bucket_name" {
  description = "Artifacts S3 bucket name"
  value       = aws_s3_bucket.artifacts.id
}

output "static_bucket_name" {
  description = "Static assets S3 bucket name"
  value       = aws_s3_bucket.static.id
}

output "artifacts_bucket_arn" {
  description = "Artifacts S3 bucket ARN"
  value       = aws_s3_bucket.artifacts.arn
}
