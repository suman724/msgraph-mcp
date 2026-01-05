variable "aws_region" {
  type        = string
  description = "AWS region to deploy into"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Environment name"
}

variable "service_name" {
  type        = string
  description = "Service name prefix"
  default     = "msgraph-mcp"
}

variable "cluster_arn" {
  type        = string
  description = "Existing ECS cluster ARN"
}

variable "task_execution_role_arn" {
  type        = string
  description = "ECS task execution role ARN"
}

variable "task_role_arn" {
  type        = string
  description = "ECS task role ARN"
}

variable "subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for ECS tasks"
}

variable "security_group_ids" {
  type        = list(string)
  description = "Security group IDs for ECS tasks"
}

variable "target_group_arn" {
  type        = string
  description = "Existing ALB target group ARN"
}

variable "container_image" {
  type        = string
  description = "Container image URI in existing registry"
}

variable "container_port" {
  type        = number
  description = "Container port for MCP server"
  default     = 8080
}

variable "desired_count" {
  type        = number
  description = "Desired ECS service count"
  default     = 2
}

variable "cpu" {
  type        = number
  description = "Fargate task CPU units"
  default     = 512
}

variable "memory" {
  type        = number
  description = "Fargate task memory (MB)"
  default     = 1024
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log retention in days"
  default     = 30
}

variable "autoscaling_min" {
  type        = number
  description = "Minimum ECS task count"
  default     = 2
}

variable "autoscaling_max" {
  type        = number
  description = "Maximum ECS task count"
  default     = 10
}

variable "cpu_target_utilization" {
  type        = number
  description = "Target CPU utilization percentage"
  default     = 60
}

variable "memory_target_utilization" {
  type        = number
  description = "Target memory utilization percentage"
  default     = 70
}

variable "redis_endpoint" {
  type        = string
  description = "Redis endpoint (host:port)"
}


variable "kms_key_alias" {
  type        = string
  description = "KMS key alias for secrets"
  default     = "alias/msgraph-mcp"
}

variable "secret_graph_client" {
  type        = string
  description = "Secrets Manager name for Graph client secret"
  default     = "msgraph-client-secret"
}

variable "secret_datadog_api_key" {
  type        = string
  description = "Secrets Manager name for Datadog API key"
  default     = "datadog-api-key"
}

variable "secret_bootstrap_value" {
  type        = string
  description = "Bootstrap secret value used for initial provisioning"
  default     = "REPLACE_ME"
}

variable "otel_exporter_endpoint" {
  type        = string
  description = "Datadog OTLP endpoint"
  default     = "https://api.datadoghq.com/api/v2/otlp"
}

variable "environment_variables" {
  type        = map(string)
  description = "Additional environment variables for the container"
  default     = {}
}
