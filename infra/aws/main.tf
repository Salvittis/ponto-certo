data "aws_ami" "ubuntu" {
  owners      = ["099720109477"] # Canonical; not a community or Marketplace AMI.
  most_recent = false

  filter {
    name   = "image-id"
    values = [var.ubuntu_ami_id]
  }
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }
  filter {
    name   = "state"
    values = ["available"]
  }
}

# The Sandbox owns IAM. Read this existing profile; do not create roles/policies.
data "aws_iam_instance_profile" "lab" {
  name = "LabInstanceProfile"
}

resource "aws_vpc" "app" {
  cidr_block           = "10.82.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "app" {
  vpc_id = aws_vpc.app.id
  tags   = { Name = "${var.name_prefix}-igw" }
}

resource "aws_subnet" "app" {
  vpc_id                  = aws_vpc.app.id
  cidr_block              = "10.82.1.0/24"
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.name_prefix}-public" }
}

resource "aws_route_table" "app" {
  vpc_id = aws_vpc.app.id
  tags   = { Name = "${var.name_prefix}-public" }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.app.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.app.id
}

resource "aws_route_table_association" "app" {
  subnet_id      = aws_subnet.app.id
  route_table_id = aws_route_table.app.id
}

resource "aws_security_group" "app" {
  name_prefix = "${var.name_prefix}-"
  description = "Public HTTP/HTTPS only; management uses outbound SSM, never SSH."
  vpc_id      = aws_vpc.app.id
  tags        = { Name = "${var.name_prefix}-web" }
}

resource "aws_vpc_security_group_ingress_rule" "web" {
  for_each          = toset(["80", "443"])
  security_group_id = aws_security_group.app.id
  description       = "Public web port ${each.value}"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = tonumber(each.value)
  to_port           = tonumber(each.value)
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "outbound" {
  security_group_id = aws_security_group.app.id
  description       = "SSM, OS/image downloads, ACME and application sources; no restrictive egress policy in this MVP."
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_instance" "app" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t2.medium"
  subnet_id                   = aws_subnet.app.id
  vpc_security_group_ids      = [aws_security_group.app.id]
  associate_public_ip_address = true
  iam_instance_profile        = data.aws_iam_instance_profile.lab.name
  monitoring                  = false
  # No key_name: SSH is neither provisioned nor opened in the security group.
  user_data                   = file("${path.module}/cloud-init.yaml")
  user_data_replace_on_change = true

  credit_specification {
    cpu_credits = "standard"
  }

  root_block_device {
    volume_type           = "gp2" # Override the Ubuntu AMI's gp3 default for the Sandbox.
    volume_size           = 32
    encrypted             = true
    delete_on_termination = true
    tags                  = { Name = "${var.name_prefix}-root" }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1 # Host SSM can use IMDS; application containers do not need LabRole.
    instance_metadata_tags      = "disabled"
  }

  tags = { Name = "${var.name_prefix}-vm" }

  # Bootstrap needs outbound connectivity immediately, before installing Docker.
  depends_on = [
    aws_route.internet,
    aws_route_table_association.app,
    aws_vpc_security_group_egress_rule.outbound,
  ]
}
