locals {
  admin_username = "pontoops"
  tags = {
    project    = "ponto-certo"
    purpose    = "fiap-gs-2026-2"
    managed_by = "terraform"
  }
}

resource "azurerm_resource_group" "ponto_certo" {
  name     = "${var.name_prefix}-rg"
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "ponto_certo" {
  name                = "${var.name_prefix}-vnet"
  location            = azurerm_resource_group.ponto_certo.location
  resource_group_name = azurerm_resource_group.ponto_certo.name
  address_space       = ["10.42.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "app" {
  name                 = "app"
  resource_group_name  = azurerm_resource_group.ponto_certo.name
  virtual_network_name = azurerm_virtual_network.ponto_certo.name
  address_prefixes     = ["10.42.1.0/24"]
}

resource "azurerm_network_security_group" "web_only" {
  name                = "${var.name_prefix}-web-only"
  location            = azurerm_resource_group.ponto_certo.location
  resource_group_name = azurerm_resource_group.ponto_certo.name
  tags                = local.tags

  security_rule {
    name                       = "HTTPS-and-ACME-only"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_ranges    = ["80", "443"]
    source_address_prefix      = "Internet"
    destination_address_prefix = "*"
  }

  # Overrides Azure's default VNet inbound allow too. No administrative port.
  security_rule {
    name                       = "Deny-all-other-inbound"
    priority                   = 200
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_public_ip" "web" {
  name                = "${var.name_prefix}-web-ip"
  location            = azurerm_resource_group.ponto_certo.location
  resource_group_name = azurerm_resource_group.ponto_certo.name
  allocation_method   = "Static"
  sku                 = "Standard"
  domain_name_label   = var.public_dns_label
  tags                = local.tags
}

resource "azurerm_network_interface" "app" {
  name                = "${var.name_prefix}-nic"
  location            = azurerm_resource_group.ponto_certo.location
  resource_group_name = azurerm_resource_group.ponto_certo.name
  tags                = local.tags

  ip_configuration {
    name                          = "app"
    subnet_id                     = azurerm_subnet.app.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.web.id
  }
}

resource "azurerm_network_interface_security_group_association" "web_only" {
  network_interface_id      = azurerm_network_interface.app.id
  network_security_group_id = azurerm_network_security_group.web_only.id
}

resource "azurerm_linux_virtual_machine" "app" {
  name                            = "${var.name_prefix}-vm"
  location                        = azurerm_resource_group.ponto_certo.location
  resource_group_name             = azurerm_resource_group.ponto_certo.name
  size                            = var.vm_size
  admin_username                  = local.admin_username
  disable_password_authentication = true
  network_interface_ids           = [azurerm_network_interface.app.id]
  provision_vm_agent              = true
  secure_boot_enabled             = true
  vtpm_enabled                    = true
  tags                            = local.tags

  admin_ssh_key {
    username   = local.admin_username
    public_key = trimspace(var.admin_public_key)
  }

  os_disk {
    name                 = "${var.name_prefix}-os"
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = 32
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = var.os_image_version
  }

  # No token, password, model credential or application secret enters cloud-init/state.
  custom_data = base64encode(file("${path.module}/cloud-init.yaml"))
  depends_on  = [azurerm_network_interface_security_group_association.web_only]
}

# This identity is for GitHub only and is deliberately NOT attached to the VM.
# The container cannot obtain deployment permissions through VM metadata.
resource "azurerm_user_assigned_identity" "github_deploy" {
  name                = "${var.name_prefix}-github-deploy"
  location            = azurerm_resource_group.ponto_certo.location
  resource_group_name = azurerm_resource_group.ponto_certo.name
  tags                = local.tags
}

resource "azurerm_federated_identity_credential" "github_production" {
  name                      = "github-production"
  user_assigned_identity_id = azurerm_user_assigned_identity.github_deploy.id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "${var.github_oidc_subject_prefix}:environment:${var.github_environment}"
}

resource "azurerm_role_definition" "deploy" {
  name        = "${var.name_prefix}-vm-deploy"
  scope       = azurerm_resource_group.ponto_certo.id
  description = "Read one FIAP VM and execute its deployment script; no network, IAM or VM creation permissions."
  permissions {
    actions = [
      "Microsoft.Compute/virtualMachines/read",
      "Microsoft.Compute/virtualMachines/instanceView/read",
      "Microsoft.Compute/virtualMachines/runCommands/read",
      "Microsoft.Compute/virtualMachines/runCommands/write",
      "Microsoft.Compute/virtualMachines/runCommands/delete",
    ]
    not_actions = []
  }
  assignable_scopes = [azurerm_resource_group.ponto_certo.id]
}

resource "azurerm_role_assignment" "deploy_one_vm" {
  scope                            = azurerm_linux_virtual_machine.app.id
  role_definition_id               = azurerm_role_definition.deploy.role_definition_resource_id
  principal_id                     = azurerm_user_assigned_identity.github_deploy.principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}
