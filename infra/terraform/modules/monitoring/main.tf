resource "google_monitoring_notification_channel" "email" {
  display_name = "${var.name_prefix} Budget Alert Email"
  type         = "email"
  labels = {
    email_address = var.notification_email
  }
}

# Budget alert for GCP spending
resource "google_billing_budget" "budget" {
  billing_account = var.billing_account_id
  display_name    = "${var.name_prefix} Monthly Budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = var.budget_amount
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.email.id]
    disable_default_iam_recipients   = false
  }
}

# Uptime check for the API
resource "google_monitoring_uptime_check_config" "api_health" {
  display_name = "${var.name_prefix} API Health Check"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/api/health"
    port         = 443
    use_ssl      = true
    validate_ssl = true
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      host = replace(var.cloud_run_api_url, "https://", "")
    }
  }
}

resource "google_monitoring_alert_policy" "api_down" {
  display_name = "${var.name_prefix} API Down"
  combiner     = "OR"
  conditions {
    display_name = "Uptime check failure"
    condition_threshold {
      filter     = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\""
      duration   = "120s"
      comparison = "COMPARISON_LT"
      threshold_value = 1
      aggregations {
        alignment_period     = "120s"
        per_series_aligner   = "ALIGN_COUNT_TRUE"
        cross_series_reducer = "REDUCE_COUNT_TRUE"
      }
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
  alert_strategy {
    auto_close = "1800s"
  }
}

# Alert for high error rate on Cloud Run
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "${var.name_prefix} High Error Rate"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run error rate > 5%"
    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND metric.labels.response_code_class=\"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_NONE"
      }
    }
  }
  notification_channels = [google_monitoring_notification_channel.email.id]
  alert_strategy {
    auto_close = "3600s"
  }
}
