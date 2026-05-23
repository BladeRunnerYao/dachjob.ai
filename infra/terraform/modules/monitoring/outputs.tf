output "notification_channel_id" {
  description = "Email notification channel ID"
  value       = google_monitoring_notification_channel.email.id
}

output "alert_policy_ids" {
  description = "Map of alert policy names to IDs"
  value = {
    high_error_rate = google_monitoring_alert_policy.high_error_rate.id
  }
}
