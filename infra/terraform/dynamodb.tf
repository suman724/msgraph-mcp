resource "aws_dynamodb_table" "tokens" {
  count        = var.create_dynamodb_tables ? 1 : 0
  name         = "${local.name_prefix}-tokens"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }
}

resource "aws_dynamodb_table" "sessions" {
  count        = var.create_dynamodb_tables ? 1 : 0
  name         = "${local.name_prefix}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "mcp_session_id"

  attribute {
    name = "mcp_session_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "delta_tokens" {
  count        = var.create_dynamodb_tables ? 1 : 0
  name         = "${local.name_prefix}-delta"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }
}

resource "aws_dynamodb_table" "idempotency" {
  count        = var.create_dynamodb_tables ? 1 : 0
  name         = "${local.name_prefix}-idempotency"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}
