resource "google_storage_bucket" "artifacts" {
  name          = "${var.name_prefix}-artifacts"
  location      = var.location
  storage_class = "STANDARD"
  labels        = var.labels

  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "static_assets" {
  name          = "${var.name_prefix}-static"
  location      = var.location
  storage_class = "STANDARD"
  labels        = var.labels

  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }
}

# Terraform state bucket is created manually by scripts/bootstrap.sh
# resource "google_storage_bucket" "terraform_state" {
#   name          = "${var.name_prefix}-terraform-state"
#   location      = var.location
#   storage_class = "STANDARD"
#   labels        = var.labels
#   uniform_bucket_level_access = true
#   versioning { enabled = true }
# }
