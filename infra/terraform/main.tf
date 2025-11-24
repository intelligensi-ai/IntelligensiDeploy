# Terraform entrypoint for IntelligensiDeploy infrastructure.

terraform {
  required_version = ">= 1.5.0"
}

provider "aws" {
  # Placeholder configuration for Phase 3 scaffolding.
  region = var.region
}

# Module stubs for future infrastructure components.
# module "gpu_instance" {
#   source = "./modules/gpu_instance"
# }
#
# module "network" {
#   source = "./modules/network"
# }
#
# module "storage" {
#   source = "./modules/storage"
# }
#
# module "monitoring" {
#   source = "./modules/monitoring"
# }
