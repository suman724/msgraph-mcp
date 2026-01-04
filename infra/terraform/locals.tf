locals {
  ddb_table_tokens      = var.create_dynamodb_tables ? aws_dynamodb_table.tokens[0].name : var.dynamodb_table_tokens
  ddb_table_sessions    = var.create_dynamodb_tables ? aws_dynamodb_table.sessions[0].name : var.dynamodb_table_sessions
  ddb_table_delta       = var.create_dynamodb_tables ? aws_dynamodb_table.delta_tokens[0].name : var.dynamodb_table_delta
  ddb_table_idempotency = var.create_dynamodb_tables ? aws_dynamodb_table.idempotency[0].name : var.dynamodb_table_idempotency
  cluster_name          = split("/", var.cluster_arn)[1]
}
