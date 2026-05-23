output "network_id" {
  description = "VPC network self-link"
  value       = google_compute_network.vpc.id
}

output "network_self_link" {
  description = "VPC network self-link (for GKE)"
  value       = google_compute_network.vpc.self_link
}

output "network_name" {
  description = "VPC network name"
  value       = google_compute_network.vpc.name
}

output "vpc_connector_id" {
  description = "VPC connector ID"
  value       = google_vpc_access_connector.connector.id
}
