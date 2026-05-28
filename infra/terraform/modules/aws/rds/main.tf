# ------------------------------------------------------------------------------
# AWS RDS – PostgreSQL 16 with pgvector
# ------------------------------------------------------------------------------
# Mirrors: GCP modules/cloud-sql, Azure modules/azure/postgres
#
# Database lives in private subnets. Security group allows ECS tasks.

resource "random_id" "db_suffix" {
  byte_length = 2
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-db-subnet"
  })
}

resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.ecs_security_group_id]
    description     = "PostgreSQL from ECS tasks"
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-rds-sg"
  })
}

resource "aws_db_parameter_group" "this" {
  name   = "${var.name_prefix}-pg16"
  family = "postgres16"

  # pgvector on RDS is available as a regular extension (CREATE EXTENSION vector).
  # It does NOT require shared_preload_libraries on AWS RDS for PostgreSQL.
  # No custom parameters needed — the default parameter group is sufficient.

  tags = var.tags
}

resource "aws_db_instance" "this" {
  identifier = "${var.name_prefix}-postgres-${random_id.db_suffix.hex}"

  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  allocated_storage     = var.allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  max_allocated_storage = var.max_allocated_storage

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible    = false
  skip_final_snapshot    = var.skip_final_snapshot
  backup_retention_period = var.backup_retention_period
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  # Enable IAM database auth (like GCP Cloud SQL IAM auth)
  iam_database_authentication_enabled = var.iam_db_auth

  # Enable automated minor version upgrades
  auto_minor_version_upgrade = true

  parameter_group_name = aws_db_parameter_group.this.name

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-postgres"
  })

  lifecycle {
    ignore_changes = [
      snapshot_identifier,
    ]
  }
}
