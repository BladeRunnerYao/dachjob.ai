name_prefix = "dachjob-az"
location          = "francecentral"

postgres_administrator_password = "ARrAy3MuDgSgBTFNurVi5ipZ"

api_image_tag      = "latest"
frontend_image_tag = "latest"
worker_image_tag   = "latest"

tags = {
  environment = "dev"
  managed_by  = "terraform"
  project     = "dachjob"
}
