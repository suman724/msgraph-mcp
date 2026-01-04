output "service_name" {
  value = aws_ecs_service.service.name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.service.name
}

output "dynamodb_tokens_table" {
  value = local.ddb_table_tokens
}

output "dynamodb_sessions_table" {
  value = local.ddb_table_sessions
}

output "dynamodb_delta_table" {
  value = local.ddb_table_delta
}

output "dynamodb_idempotency_table" {
  value = local.ddb_table_idempotency
}

output "kms_key_arn" {
  value = aws_kms_key.service.arn
}
