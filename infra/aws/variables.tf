variable "allowed_account_ids" {
  description = "Exactly one authorized AWS Academy Sandbox account; never a personal or corporate account."
  type        = list(string)
  validation {
    condition     = length(var.allowed_account_ids) == 1 && alltrue([for account in var.allowed_account_ids : can(regex("^[0-9]{12}$", account))])
    error_message = "Provide exactly one 12-digit Academy account ID verified with STS and the active lab."
  }
}

variable "ubuntu_ami_id" {
  description = "Explicit Ubuntu Server 24.04 AMD64 AMI resolved in us-east-1 before planning; owner/architecture/name are verified by the data source."
  type        = string
  validation {
    condition     = can(regex("^ami-[0-9a-f]{17}$", var.ubuntu_ami_id))
    error_message = "Pin a real modern AMI ID; latest or an SSM alias is not accepted here."
  }
}

variable "availability_zone" {
  description = "Authorized us-east-1 availability zone where t2.medium is offered, verified during lab preflight."
  type        = string
  validation {
    condition     = can(regex("^us-east-1[a-z]$", var.availability_zone))
    error_message = "Use an available standard us-east-1 availability zone; Local/Wavelength Zones are outside this lab."
  }
}

variable "name_prefix" {
  description = "Prefix for dedicated, disposable Academy resources."
  type        = string
  default     = "ponto-certo-fiap-aws"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{3,30}$", var.name_prefix))
    error_message = "Use 4-31 lowercase letters, digits or hyphens."
  }
}
