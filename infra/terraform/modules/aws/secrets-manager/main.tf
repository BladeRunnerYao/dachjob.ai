# ------------------------------------------------------------------------------
# AWS Secrets Manager
# ------------------------------------------------------------------------------
# Mirrors: GCP modules/secret-manager, Azure modules/azure/key-vault
#
# Stores application secrets. Auto-generates DB password.
# ECS tasks access secrets via IAM.

resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "aws_secretsmanager_secret" "db_password" {
  name = "${var.name_prefix}-db-password"

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}

# ------------------------------------------------------------------------------
# Application secrets (populated manually or via CI)
# ------------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "app" {
  for_each = toset(var.secret_names)

  name = "${var.name_prefix}-${each.key}"

  tags = var.tags
}
