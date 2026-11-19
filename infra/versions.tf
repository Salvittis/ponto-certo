terraform {
  required_version = ">= 1.9.0, < 2.0.0"
  # tf.sh supplies an absolute path outside this repository.
  backend "local" {}
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "5.14.0"
    }
  }
}

provider "azurerm" {
  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
  features {}
}

data "azurerm_client_config" "current" {}
