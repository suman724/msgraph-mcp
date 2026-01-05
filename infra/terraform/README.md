# Terraform - ECS Service (Existing VPC/Cluster/ALB)

This Terraform config provisions the ECS service, task definition, and Secrets Manager secrets for the MCP server. It assumes the VPC, ECS cluster, ALB, and target group already exist.

## Quick start

1. Copy an env file and fill in values.
2. Run Terraform with the desired env file.

```bash
terraform init
terraform apply -var-file=env/dev.tfvars
```

## Inputs

See `variables.tf` for the full list. Required inputs:

- `environment`
- `cluster_arn`
- `task_execution_role_arn`
- `task_role_arn`
- `subnet_ids`
- `security_group_ids`
- `target_group_arn`
- `container_image`
- `redis_endpoint`
- `secret_redis_encryption_key`

## Notes

- Secrets are created with a bootstrap value (`REPLACE_ME`). Update them after provisioning.
