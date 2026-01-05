locals {
  cluster_name = split("/", var.cluster_arn)[1]
}
