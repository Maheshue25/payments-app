terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
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

module "dns" {
  source      = "../../modules/dns"
  domain_name = "erothi.online"
}

output "route53_nameservers" {
  description = "Assign these nameservers to your domain registrar (e.g., Hostinger, GoDaddy, Namecheap)"
  value       = module.dns.name_servers
}

output "acm_certificate_arn" {
  description = "ACM Certificate ARN to be injected into Helm Ingress"
  value       = module.dns.certificate_arn
}

# Configure Helm provider at the root level using EKS module outputs
provider "helm" {
  kubernetes = {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
      command     = "aws"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    command     = "aws"
  }
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "ai_agent_irsa_arn" {
  description = "Use this ARN to annotate the Helm chart ServiceAccount"
  value       = module.eks.ai_agent_role_arn
}