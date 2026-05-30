output "host" {
  description = "Redis host IP address"
  value       = google_redis_instance.redis.host
}

output "port" {
  description = "Redis port"
  value       = google_redis_instance.redis.port
}

output "id" {
  description = "Redis instance ID"
  value       = google_redis_instance.redis.id
}
