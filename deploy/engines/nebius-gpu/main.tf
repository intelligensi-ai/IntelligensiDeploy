terraform {
  required_version = ">= 1.3.0"
}

locals {
  service_url = var.public_ip_override != "" ? "http://${var.public_ip_override}:${var.service_port}" : null
}

# TODO(nebius): replace this terraform_data placeholder with the real Nebius
# provider/resource graph once provider credentials, resource names, and the
# target VM shape are confirmed. This keeps the engine safe to extend without
# inventing unsupported resource attributes today.
resource "terraform_data" "deployment_intent" {
  input = {
    provider          = "nebius"
    project_id        = var.project_id
    folder_id         = var.folder_id
    api_token_present = var.api_token != ""
    region            = var.region
    zone              = var.zone
    instance_name     = var.instance_name
    gpu_shape         = var.gpu_shape
    disk_size_gb      = var.disk_size_gb
    ssh_username      = var.ssh_username
    ssh_public_key    = var.ssh_public_key_path
    container_image   = var.container_image
    service_port      = var.service_port
    public_ip_override = var.public_ip_override
  }
}

