output "region" {
  value = "us-east-1"
}

output "instance_id" {
  description = "Only this instance may be targeted by the Academy deployment."
  value       = aws_instance.app.id
}

output "instance_type" {
  value = aws_instance.app.instance_type
}

output "ubuntu_ami_id" {
  value = data.aws_ami.ubuntu.id
}

output "ubuntu_ami_name" {
  value = data.aws_ami.ubuntu.name
}

output "instance_profile_name" {
  value = data.aws_iam_instance_profile.lab.name
}

output "public_ip" {
  description = "Ephemeral IPv4; may change after stop/start and disappears when the Sandbox ends."
  value       = aws_instance.app.public_ip
}

output "aws_public_dns" {
  description = "AWS-assigned DNS name; not a claim that an HTTPS certificate exists."
  value       = aws_instance.app.public_dns
}

output "public_host" {
  description = "Suggested temporary sslip.io hostname; verify DNS and ACME before declaring publication."
  value       = "${replace(aws_instance.app.public_ip, ".", "-")}.sslip.io"
}

output "public_url" {
  description = "Deployment target only until the external HTTPS/model smoke passes."
  value       = "https://${replace(aws_instance.app.public_ip, ".", "-")}.sslip.io"
}

output "security_group_id" {
  value = aws_security_group.app.id
}

output "vpc_id" {
  value = aws_vpc.app.id
}
