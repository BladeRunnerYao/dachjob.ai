# ------------------------------------------------------------------------------
# AWS ElastiCache – Redis 7
# ------------------------------------------------------------------------------
# Mirrors: GCP modules/memorystore, Azure modules/azure/redis
#
# Single-node Redis cluster in private subnets for Celery broker + cache.

resource "aws_security_group" "redis" {
  name        = "${var.name_prefix}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.ecs_security_group_id]
    description     = "Redis from ECS tasks"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis-sg"
  })
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name_prefix}-redis-subnet"
  subnet_ids = var.private_subnet_ids

  tags = var.tags
}

resource "aws_elasticache_cluster" "this" {
  cluster_id           = "${var.name_prefix}-redis"
  engine               = "redis"
  node_type            = var.node_type
  num_cache_nodes      = var.num_cache_nodes
  parameter_group_name = var.parameter_group_name
  engine_version       = var.engine_version
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.redis.id]

  # No encryption in transit for dev (matching GCP Memorystore no-transit-encryption)
  # Enable for staging/prod by setting the variable
  transit_encryption_enabled = var.transit_encryption_enabled

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-redis"
  })
}
