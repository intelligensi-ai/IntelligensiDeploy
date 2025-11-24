terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
  }
}

locals {
  gpu_profile = {
    type   = var.gpu_type
    disk   = var.disk_size
    region = var.region
    name   = var.instance_name
  }
}

resource "random_id" "instance" {
  byte_length = 4
}

resource "random_integer" "public_ip_octet" {
  min = 10
  max = 200
}

resource "terraform_data" "gpu_instance" {
  input = local.gpu_profile
}

output "instance_id" {
  description = "Synthetic identifier for the GPU instance"
  value       = random_id.instance.hex
}

output "public_ip" {
  description = "Documentation-only public IP placeholder"
  value       = format("198.51.100.%d", random_integer.public_ip_octet.result)
}
