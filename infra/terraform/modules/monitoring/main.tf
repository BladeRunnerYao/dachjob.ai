resource "google_monitoring_notification_channel" "email" {
  display_name = "${var.name_prefix} Budget Alert Email"
  type         = "email"
  labels = {
    email_address = var.notification_email
  }
}

# Alert for high error rate on Cloud Run
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "${var.name_prefix} High Error Rate"
  combiner     = "OR"
  conditions {
    display_name = "Cloud Run 5xx rate"
    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" AND resource.type=\"cloud_run_revision\" AND metric.labels.response_code_class=\"5xx\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5
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
