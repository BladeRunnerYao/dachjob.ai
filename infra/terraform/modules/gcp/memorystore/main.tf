resource "google_redis_instance" "redis" {
  name           = "${var.name_prefix}-redis"
  tier           = var.redis_tier
  memory_size_gb = var.redis_memory_size_gb
  region         = var.region
  labels         = var.labels

  authorized_network = var.network_id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  redis_version           = "REDIS_7_0"
  display_name            = "${var.name_prefix} Redis"
  transit_encryption_mode = "DISABLED"
}
