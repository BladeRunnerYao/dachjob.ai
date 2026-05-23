terraform {
  backend "gcs" {
    # Configure per environment:
    # bucket = "dachjob-ai-terraform-state"
    # prefix = "dev"
  }
}
