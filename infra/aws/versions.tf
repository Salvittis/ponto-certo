terraform {
  required_version = ">= 1.9.0, < 2.0.0"
  # The AWS wrapper supplies a path outside Git and separate from Azure state.
  backend "local" {}
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.73.0"
    }
  }
}

provider "aws" {
  region              = "us-east-1"
  allowed_account_ids = var.allowed_account_ids

  # Credentials come only from the active AWS Academy session, outside Terraform.
  default_tags {
    tags = {
      project     = "ponto-certo"
      environment = "aws-academy"
      managed_by  = "terraform"
      purpose     = "fiap-cloud"
    }
  }
}
