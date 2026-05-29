# ------------------------------------------------------------------------------
# AWS ECS – Elastic Container Service (Fargate)
# ------------------------------------------------------------------------------
# Mirrors: GCP modules/cloud-run + modules/gke, Azure modules/azure/container-apps
#
# ECS Fargate cluster running 3 services: API, Frontend, Worker.
# Single ALB with path-based routing: /api/* → API, /* → Frontend.
# Worker is internal-only (no public ingress).

# ===========================================================================
# ECS Cluster
# ===========================================================================
resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = var.tags
}

# ===========================================================================
# Security Groups
# ===========================================================================
resource "aws_security_group" "alb" {
  name        = "${var.name_prefix}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP from internet"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from internet"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-alb-sg"
  })
}

# Security group for ECS tasks is created in root main.tf and passed via
# var.ecs_security_group_id to break the circular dependency between
# ECS ↔ RDS/ElastiCache. We add ALB ingress rules here.
resource "aws_security_group_rule" "ecs_api_from_alb" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = aws_security_group.alb.id
  description              = "API from ALB"
}

resource "aws_security_group_rule" "ecs_frontend_from_alb" {
  type                     = "ingress"
  from_port                = 3000
  to_port                  = 3000
  protocol                 = "tcp"
  security_group_id        = var.ecs_security_group_id
  source_security_group_id = aws_security_group.alb.id
  description              = "Frontend from ALB"
}

# ===========================================================================
# Application Load Balancer
# ===========================================================================
resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-alb"
  })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name_prefix}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/api/health"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 5
    matcher             = "200"
  }

  tags = var.tags
}

resource "aws_lb_target_group" "frontend" {
  name        = "${var.name_prefix}-frontend-tg"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 5
    matcher             = "200"
  }

  tags = var.tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

# ===========================================================================
# IAM Roles
# ===========================================================================

# Task execution role – pulls images from ECR, writes to CloudWatch
resource "aws_iam_role" "ecs_execution" {
  name = "${var.name_prefix}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Additional policy for Secrets Manager access during task startup
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "${var.name_prefix}-execution-secrets"
  role = aws_iam_role.ecs_execution.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Resource = var.secret_arns
    }]
  })
}

# Task role – runtime access to S3, Secrets Manager, Bedrock (optional LLM)
resource "aws_iam_role" "ecs_task" {
  name = "${var.name_prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "${var.name_prefix}-task-policy"
  role = aws_iam_role.ecs_task.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
        ]
        Resource = [
          var.artifacts_bucket_arn,
          "${var.artifacts_bucket_arn}/*",
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Resource = var.secret_arns
      },
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "*"
      },
    ]
  })
}

# ===========================================================================
# Task Definitions
# ===========================================================================

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name_prefix}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "api"
      image = var.api_image
      portMappings = [{
        containerPort = 8000
        protocol      = "tcp"
      }]
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "APP_ENV", value = var.environment },
        { name = "LOG_LEVEL", value = var.log_level },
        { name = "LOG_JSON", value = "true" },
        { name = "ERROR_LOG_TO_FILE", value = "true" },
        { name = "ERROR_LOG_DIR", value = "/tmp/dachjob-error-logs" },
        { name = "STORAGE_PROVIDER", value = "s3" },
        { name = "S3_BUCKET_NAME", value = var.artifacts_bucket_name },
        { name = "S3_ENDPOINT_URL", value = "" },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "WORKER_ENABLED", value = var.worker_enabled },
        { name = "WORKER_FALLBACK_TO_SYNC", value = "true" },
        { name = "REDIS_ENABLED", value = var.redis_enabled ? "true" : "false" },
        { name = "REDIS_URL", value = var.redis_url },
        { name = "DATABASE_URL", value = var.database_url },
        { name = "CORS_ORIGINS", value = var.cors_origins },
        { name = "LLM_PROVIDER", value = var.llm_provider },
        { name = "RESEND_FROM_EMAIL", value = var.resend_from_email },
      ]
      secrets = concat(
        var.jwt_secret_arn != "" ? [{ name = "JWT_SECRET", valueFrom = var.jwt_secret_arn }] : [],
        var.deepseek_api_key_arn != "" ? [{ name = "DEEPSEEK_API_KEY", valueFrom = var.deepseek_api_key_arn }] : [],
        var.resend_api_key_arn != "" ? [{ name = "RESEND_API_KEY", valueFrom = var.resend_api_key_arn }] : [],
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.api_log_group_name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])

  tags = var.tags
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.name_prefix}-frontend"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.frontend_cpu
  memory                   = var.frontend_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "frontend"
      image = var.frontend_image
      portMappings = [{
        containerPort = 3000
        protocol      = "tcp"
      }]
      environment = [
        { name = "INTERNAL_API_BASE_URL", value = "http://${aws_lb.this.dns_name}" },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.frontend_log_group_name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "frontend"
        }
      }
    }
  ])

  tags = var.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name_prefix}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name    = "worker"
      image   = var.worker_image
      command = ["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "APP_ENV", value = var.environment },
        { name = "LOG_LEVEL", value = var.log_level },
        { name = "LOG_JSON", value = "true" },
        { name = "STORAGE_PROVIDER", value = "s3" },
        { name = "S3_BUCKET_NAME", value = var.artifacts_bucket_name },
        { name = "S3_ENDPOINT_URL", value = "" },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "REDIS_URL", value = var.redis_url },
        { name = "REDIS_ENABLED", value = "true" },
        { name = "DATABASE_URL", value = var.database_url },
      ]
      secrets = concat(
        var.jwt_secret_arn != "" ? [{ name = "JWT_SECRET", valueFrom = var.jwt_secret_arn }] : [],
        var.deepseek_api_key_arn != "" ? [{ name = "DEEPSEEK_API_KEY", valueFrom = var.deepseek_api_key_arn }] : [],
      )
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.worker_log_group_name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }
    }
  ])

  tags = var.tags
}

# ===========================================================================
# ECS Services
# ===========================================================================

resource "aws_ecs_service" "api" {
  name            = "${var.name_prefix}-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  lifecycle {
    ignore_changes = [
      desired_count, # Allow auto-scaling to manage this
    ]
  }

  tags = var.tags
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.name_prefix}-frontend"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.frontend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 3000
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  lifecycle {
    ignore_changes = [
      desired_count,
    ]
  }

  tags = var.tags
}

resource "aws_ecs_service" "worker" {
  name            = "${var.name_prefix}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_security_group_id]
    assign_public_ip = false
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  lifecycle {
    ignore_changes = [
      desired_count,
    ]
  }

  tags = var.tags
}

# ===========================================================================
# GitHub Actions OIDC – IAM Role for CI/CD
# ===========================================================================
# Mirrors: GCP Workload Identity Federation, Azure AD OIDC federated credential
# Allows GitHub Actions to push images to ECR, update ECS services, run tasks.

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "github_actions" {
  name = "${var.name_prefix}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "github_actions" {
  name = "${var.name_prefix}-github-actions-policy"
  role = aws_iam_role.github_actions.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetRepositoryPolicy",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
          "ecr:DescribeImages",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:RegisterTaskDefinition",
          "ecs:RunTask",
          "ecs:DescribeTasks",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole",
        ]
        Resource = [
          aws_iam_role.ecs_execution.arn,
          aws_iam_role.ecs_task.arn,
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Resource = var.secret_arns
      },
      {
        Effect = "Allow"
        Action = [
          "cloudfront:ListDistributions",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeTargetGroups",
        ]
        Resource = "*"
      },
    ]
  })
}
