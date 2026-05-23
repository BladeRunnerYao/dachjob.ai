resource "google_container_cluster" "cluster" {
  name     = "${var.name_prefix}-cluster"
  location = var.region

  enable_autopilot = true

  network         = var.network_id
  networking_mode = "VPC_NATIVE"

  release_channel {
    channel = "REGULAR"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  ip_allocation_policy {
    cluster_ipv4_cidr_block  = ""
    services_ipv4_cidr_block = ""
  }

  deletion_protection = false
}

resource "google_gke_hub_membership" "membership" {
  count = var.register_to_fleet ? 1 : 0

  membership_id = "${var.name_prefix}-cluster"
  location      = var.region
  endpoint {
    gke_cluster {
      resource_link = "//container.googleapis.com/${google_container_cluster.cluster.id}"
    }
  }
}
