variable "cluster_name" {
  type        = string
  description = "Name of the EKS cluster"
}

variable "cluster_version" {
  type        = string
  default     = "1.31"
  description = "Kubernetes control plane version"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where EKS will be deployed"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private Subnet IDs for worker nodes"
}

variable "agent_namespace" {
  type        = string
  default     = "payments"
  description = "Kubernetes namespace for AI Support Agent"
}

variable "agent_service_account" {
  type        = string
  default     = "support-ai-agent-sa"
  description = "Kubernetes ServiceAccount bound to Bedrock execution role"
}

# 1. EKS Cluster Definition
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  vpc_id                   = var.vpc_id
  subnet_ids               = var.private_subnet_ids
  control_plane_subnet_ids = var.private_subnet_ids

  enable_cluster_creator_admin_permissions = true

  # Workload isolation across managed node groups
  eks_managed_node_groups = {
    system = {
      instance_types = ["t3.medium"]
      min_size       = 2
      max_size       = 4
      desired_size   = 2
      labels = {
        role = "system-tools"
      }
      taints = []
    }
    workloads = {
      instance_types = ["m6i.xlarge"]
      min_size       = 2
      max_size       = 6
      desired_size   = 2
      labels = {
        role = "application-agent"
      }
      taints = []
    }
  }

  tags = {
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

# 2. AgentOps IRSA: IAM Role for Service Accounts for Bedrock LLM Inference
resource "aws_iam_role" "ai_agent_irsa" {
  name = "${var.cluster_name}-support-ai-agent-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = module.eks.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:${var.agent_namespace}:${var.agent_service_account}"
            "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

# Least-privilege IAM policy allowing only Bedrock model execution
resource "aws_iam_policy" "agent_bedrock_policy" {
  name        = "${var.cluster_name}-bedrock-agent-policy"
  description = "Allows support AI agent pods to query Bedrock foundation models"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "agent_bedrock_attach" {
  role       = aws_iam_role.ai_agent_irsa.name
  policy_arn = aws_iam_policy.agent_bedrock_policy.arn
}

output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  value = module.eks.cluster_certificate_authority_data
}

output "oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}

output "ai_agent_role_arn" {
  description = "The ARN to annotate the Kubernetes ServiceAccount with"
  value       = aws_iam_role.ai_agent_irsa.arn
}

# 1. IAM Policy for AWS Load Balancer Controller
resource "aws_iam_policy" "aws_lb_controller" {
  name        = "${var.cluster_name}-AWSLoadBalancerControllerIAMPolicy"
  description = "Permissions required by the AWS Load Balancer Controller to manage ALBs/NLBs"

  # Official AWS Load Balancer Controller Policy document
  policy = file("${path.module}/iam_alb_policy.json")
}

# 2. IRSA Role for Load Balancer Controller ServiceAccount
resource "aws_iam_role" "aws_lb_controller_irsa" {
  name = "${var.cluster_name}-aws-lb-controller-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = module.eks.oidc_provider_arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
            "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "aws_lb_controller_attach" {
  role       = aws_iam_role.aws_lb_controller_irsa.name
  policy_arn = aws_iam_policy.aws_lb_controller.arn
}

# 3. Helm Release to install the controller automatically into kube-system

resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = "1.7.2"
  namespace  = "kube-system"

  set = [
    {
      name  = "clusterName"
      value = module.eks.cluster_name
    },
    {
      name  = "serviceAccount.create"
      value = "true"
    },
    {
      name  = "serviceAccount.name"
      value = "aws-load-balancer-controller"
    },
    {
      name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
      value = aws_iam_role.aws_lb_controller_irsa.arn
    }
  ]

  depends_on = [
    module.eks,
    aws_iam_role_policy_attachment.aws_lb_controller_attach
  ]
}