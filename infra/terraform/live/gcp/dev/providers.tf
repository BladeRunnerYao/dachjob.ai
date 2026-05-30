provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google" {
  alias   = "billing"
  project = var.project_id
  region  = var.region
}
