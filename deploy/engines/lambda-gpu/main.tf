terraform {
  required_providers {
    lambdalabs = {
      source = "lambdal/lambdalabs"
      version = "~> 1.5"
    }
  }

  required_version = ">= 1.3.0"
}

provider "lambdalabs" {
  api_key = var.lamda_api_key
}

module "gpu" {
  source     = "../../modules/gpu-instance"
  gpu_type   = var.gpu_type
  ssh_key    = var.ssh_key
  instance_count = var.instance_count
}

output "gpu_public_ips" {
  value = module.gpu.public_ips
}
