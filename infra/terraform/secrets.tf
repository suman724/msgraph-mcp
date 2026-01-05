resource "aws_kms_key" "service" {
  description             = "KMS key for ${local.name_prefix} secrets"
  deletion_window_in_days = 10
}

resource "aws_kms_alias" "service" {
  name          = var.kms_key_alias
  target_key_id = aws_kms_key.service.key_id
}

resource "aws_secretsmanager_secret" "graph_client" {
  name       = "${local.name_prefix}-${var.secret_graph_client}"
  kms_key_id = aws_kms_key.service.arn
}

resource "aws_secretsmanager_secret_version" "graph_client" {
  secret_id     = aws_secretsmanager_secret.graph_client.id
  secret_string = var.secret_bootstrap_value
}

resource "aws_secretsmanager_secret" "datadog_api_key" {
  name       = "${local.name_prefix}-${var.secret_datadog_api_key}"
  kms_key_id = aws_kms_key.service.arn
}

resource "aws_secretsmanager_secret_version" "datadog_api_key" {
  secret_id     = aws_secretsmanager_secret.datadog_api_key.id
  secret_string = var.secret_bootstrap_value
}

resource "aws_secretsmanager_secret" "redis_encryption_key" {
  name       = "${local.name_prefix}-${var.secret_redis_encryption_key}"
  kms_key_id = aws_kms_key.service.arn
}

resource "aws_secretsmanager_secret_version" "redis_encryption_key" {
  secret_id     = aws_secretsmanager_secret.redis_encryption_key.id
  secret_string = var.secret_bootstrap_value
}
