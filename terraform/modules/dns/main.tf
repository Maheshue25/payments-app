# Language: HCL (terraform/modules/dns/main.tf)
variable "domain_name" {
  type        = string
  description = "The primary domain name (e.g., erothi.online)"
}

variable "hosted_zone_id" {
  type        = string
  default     = "Z072927920R4QMEK1JA6O"
  description = "Exact Route 53 Hosted Zone ID to prevent duplicate-zone ambiguity"
}

# 1. Look up the exact Route 53 Public Hosted Zone by ID ONLY (no name or private_zone attributes)
data "aws_route53_zone" "primary" {
  zone_id = var.hosted_zone_id
}

# 2. Look up the existing ISSUED ACM SSL/TLS Certificate
data "aws_acm_certificate" "cert" {
  domain      = var.domain_name
  statuses    = ["ISSUED"]
  most_recent = true
}

# ----------------- Outputs -----------------
output "zone_id" {
  value = data.aws_route53_zone.primary.zone_id
}

output "name_servers" {
  value = data.aws_route53_zone.primary.name_servers
}

output "certificate_arn" {
  value = data.aws_acm_certificate.cert.arn
}