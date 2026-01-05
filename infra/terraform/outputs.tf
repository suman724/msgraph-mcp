output "service_name" {
  value = aws_ecs_service.service.name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.service.name
}

output "kms_key_arn" {
  value = aws_kms_key.service.arn
}
