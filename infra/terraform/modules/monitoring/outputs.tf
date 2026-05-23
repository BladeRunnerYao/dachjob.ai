output "notification_channel_id" {
  description = "Email notification channel ID"
  value       = google_monitoring_notification_channel.email.id
}

output "budget_id" {
  description = "Billing budget ID"
  value       = google_billing_budget.budget.id
}

output "alert_policy_ids" {
  description = "Map of alert policy names to IDs"
  value = {
    api_down        = google_monitoring_alert_policy.api_down.id
    high_error_rate = google_monitoring_alert_policy.high_error_rate.id
  }
}
