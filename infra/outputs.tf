output "subscription_id" {
  value = var.subscription_id
}

output "tenant_id" {
  value = data.azurerm_client_config.current.tenant_id
}

output "github_client_id" {
  value = azurerm_user_assigned_identity.github_deploy.client_id
}

output "github_oidc_subject" {
  value = azurerm_federated_identity_credential.github_production.subject
}

output "resource_group" {
  value = azurerm_resource_group.ponto_certo.name
}

output "vm_name" {
  value = azurerm_linux_virtual_machine.app.name
}

output "vm_id" {
  value = azurerm_linux_virtual_machine.app.id
}

output "public_hostname" {
  value = azurerm_public_ip.web.fqdn
}

output "public_ip" {
  value = azurerm_public_ip.web.ip_address
}

output "public_url" {
  description = "Becomes functional only after security-approved Compose deployment and TLS issuance."
  value       = "https://${azurerm_public_ip.web.fqdn}"
}

output "location" {
  value = azurerm_resource_group.ponto_certo.location
}

output "os_image_version" {
  value = var.os_image_version
}
