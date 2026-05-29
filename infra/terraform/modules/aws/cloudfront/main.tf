# ------------------------------------------------------------------------------
# AWS CloudFront – CDN Distribution
# ------------------------------------------------------------------------------
# Creates a CloudFront distribution in front of the ALB.
#
# Key design decisions:
# - API paths (/api/*) use CachingDisabled + AllViewerExceptHostHeader
#   so Authorization and other auth headers are forwarded to the origin
# - Default behavior (frontend) uses a short-TTL cache policy
# - Origin protocol is HTTP-only since the ALB only listens on port 80

# Cache policy: no caching for API requests
resource "aws_cloudfront_cache_policy" "api_no_cache" {
  name        = "${var.name_prefix}-api-no-cache"
  min_ttl     = 0
  default_ttl = 0
  max_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "none"
    }
  }
}

# Origin request policy: forward all viewer headers including Authorization
# Uses the AWS managed policy ID "b689b0a8-53d0-40ab-baf2-68738e2966ac"
# which is AllViewerExceptHostHeader. We create our own with the same behavior
# so the module is self-contained without hardcoding managed policy IDs.
resource "aws_cloudfront_origin_request_policy" "forward_all_headers" {
  name = "${var.name_prefix}-forward-all-headers"

  cookies_config {
    cookie_behavior = "all"
  }
  headers_config {
    header_behavior = "allViewerAndWhitelistCloudFront"
    headers {
      items = ["CloudFront-Forwarded-Proto"]
    }
  }
  query_strings_config {
    query_string_behavior = "all"
  }
}

# Cache policy for frontend: short TTL with standard caching
resource "aws_cloudfront_cache_policy" "frontend_cache" {
  name        = "${var.name_prefix}-frontend-cache"
  min_ttl     = 0
  default_ttl = 60
  max_ttl     = 86400

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "all"
    }
  }
}

resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = ""
  comment             = "${var.name_prefix} distribution"
  price_class         = "PriceClass_100" # US/Europe/Israel only (cheapest)

  origin {
    domain_name = var.alb_dns_name
    origin_id   = "alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # API behavior: /api/* — no caching, forward all headers (including Authorization)
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    cache_policy_id          = aws_cloudfront_cache_policy.api_no_cache.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.forward_all_headers.id

    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  # Default behavior: frontend — light caching
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    cache_policy_id          = aws_cloudfront_cache_policy.frontend_cache.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.forward_all_headers.id

    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = var.tags
}
