terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6"
    }
  }

  backend "s3" {
    # Configured via backend.conf at init time
    # bucket         = "dachjob-dev-terraform-state"
    # key            = "aws/dev/terraform.tfstate"
    # region         = "eu-west-1"
    # encrypt        = true
    # dynamodb_table = "dachjob-dev-terraform-lock"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = var.tags
  }
}
