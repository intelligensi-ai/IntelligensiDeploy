terraform {
  required_version = ">= 1.5.0"

  required_providers {
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.0"
    }
  }

  backend "local" {
    path = "state/terraform.tfstate"
  }
}

provider "random" {}

module "gpu_instance" {
  source        = "./modules/gpu_instance"
  gpu_type      = var.gpu_type
  disk_size     = var.disk_size
  region        = var.region
  instance_name = var.instance_name
}

output "gpu_public_ip" {
  description = "Published IP for the GPU instance"
  value       = module.gpu_instance.public_ip
}

output "gpu_instance_id" {
  description = "Identifier for the GPU resource"
  value       = module.gpu_instance.instance_id
}
