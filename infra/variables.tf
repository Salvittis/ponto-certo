variable "subscription_id" {
  description = "Academic Azure for Students subscription; never use TBC billing."
  type        = string
  validation {
    condition     = can(regex("^[0-9a-fA-F-]{36}$", var.subscription_id))
    error_message = "Provide the authorized academic Azure subscription UUID."
  }
}

variable "name_prefix" {
  description = "Names of the isolated FIAP resource group and its resources."
  type        = string
  default     = "ponto-certo-fiap"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{3,30}$", var.name_prefix))
    error_message = "Use 4-31 lowercase letters, numbers or hyphens."
  }
}

variable "location" {
  description = "Candidate region; confirm subscription policy and SKU capacity before apply."
  type        = string
  default     = "eastus2"
}

variable "vm_size" {
  description = "2-vCPU/4-GiB academic VM; candidate SKUs must pass the subscription preflight."
  type        = string
  default     = "Standard_B2als_v2"
  validation {
    condition     = contains(["Standard_B2als_v2", "Standard_B2s"], var.vm_size)
    error_message = "Use an assessed 2-vCPU/4-GiB SKU; re-estimate and review before expanding capacity."
  }
}

variable "public_dns_label" {
  description = "Unique DNS label in the region; Azure supplies the cloudapp.azure.com suffix."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,50}[a-z0-9]$", var.public_dns_label))
    error_message = "Use a lowercase DNS label with 4-52 characters."
  }
}

variable "admin_public_key" {
  description = "Public SSH key only, required by Azure even though no inbound SSH port is allowed."
  type        = string
  validation {
    condition     = can(regex("^ssh-(ed25519|rsa) [A-Za-z0-9+/=]+( .*)?$", trimspace(var.admin_public_key)))
    error_message = "Pass one SSH public key, never a private key or password."
  }
}

variable "os_image_version" {
  description = "Canonical Ubuntu 24.04 image version resolved and recorded before apply, e.g. from az vm image list."
  type        = string
  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", var.os_image_version))
    error_message = "Pin a real numeric Ubuntu image version; latest is not accepted for reproducibility."
  }
}

variable "github_repository" {
  description = "Exact GitHub owner/repository that can assume the deploy identity."
  type        = string
  default     = "Salvittis/ponto-certo"
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use owner/repository without URL or wildcards."
  }
}

variable "github_environment" {
  description = "GitHub environment; configure it to permit only main before enabling deployment."
  type        = string
  default     = "production"
  validation {
    condition     = can(regex("^[A-Za-z0-9_-]+$", var.github_environment))
    error_message = "Use an environment name without OIDC subject separators or wildcards."
  }
}
