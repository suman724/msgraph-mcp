resource "aws_cloudwatch_log_group" "service" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_task_definition" "service" {
  family                   = local.name_prefix
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "mcp"
      image     = var.container_image
      essential = true
      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]
      environment = concat([
        { name = "ENVIRONMENT", value = var.environment },
        { name = "AWS_REGION", value = var.aws_region },
        { name = "REDIS_ENDPOINT", value = var.redis_endpoint },
        { name = "OTEL_EXPORTER_OTLP_ENDPOINT", value = var.otel_exporter_endpoint },
        { name = "DD_SERVICE", value = local.name_prefix },
        { name = "DD_ENV", value = var.environment },
        { name = "DD_VERSION", value = "0.1.0" }
      ], [for k, v in var.environment_variables : { name = k, value = v }])
      secrets = [
        {
          name      = "GRAPH_CLIENT_SECRET"
          valueFrom = aws_secretsmanager_secret_version.graph_client.arn
        },
        {
          name      = "DATADOG_API_KEY"
          valueFrom = aws_secretsmanager_secret_version.datadog_api_key.arn
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.service.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "service" {
  name            = local.name_prefix
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.service.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "mcp"
    container_port   = var.container_port
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200
}
