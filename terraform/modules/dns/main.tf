variable "domain_name" {
  type        = string
  description = "The primary domain name (e.g., erothi.online)"
}

# 1. Route 53 Public Hosted Zone
resource "aws_route53_zone" "primary" {
  name          = var.domain_name
  force_destroy = false

  tags = {
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

# 2. ACM SSL/TLS Certificate (Apex and Wildcard)
resource "aws_acm_certificate" "cert" {
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Environment = "production"
    ManagedBy   = "Terraform"
  }
}

# 3. Automated DNS Validation Records
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.cert.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = aws_route53_zone.primary.zone_id
}

# 4. Certificate Validation Waiter
resource "aws_acm_certificate_validation" "cert_validation" {
  certificate_arn         = aws_acm_certificate.cert.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# ----------------- Outputs -----------------
output "zone_id" {
  value = aws_route53_zone.primary.zone_id
}

output "name_servers" {
  value = aws_route53_zone.primary.name_servers
}

output "certificate_arn" {
  value = aws_acm_certificate_validation.cert_validation.certificate_arn
}