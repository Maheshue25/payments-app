terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

locals {
  cluster_name = "payments-production-eks"
}

module "vpc" {
  source             = "../../modules/vpc"
  cluster_name       = local.cluster_name
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["${var.aws_region}a", "${var.aws_region}b", "${var.aws_region}c"]
}

module "eks" {
  source                = "../../modules/eks"
  cluster_name          = local.cluster_name
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnets
  agent_namespace       = "payments"
  agent_service_account = "support-ai-agent-sa"
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "ai_agent_irsa_arn" {
  description = "Use this ARN to annotate the Helm chart ServiceAccount"
  value       = module.eks.ai_agent_role_arn
}