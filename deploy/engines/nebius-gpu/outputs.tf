output "instance_name" {
  description = "Nebius instance name."
  value       = var.instance_name
}

output "instance_id" {
  description = "Terraform placeholder resource id for the Nebius deployment intent."
  value       = terraform_data.deployment_intent.id
}

output "public_ip" {
  description = "Public IP for the Nebius GPU node when known."
  value       = var.public_ip_override != "" ? var.public_ip_override : null
}

output "service_url" {
  description = "ComfyUI URL derived from public IP and service port when available."
  value       = var.public_ip_override != "" ? "http://${var.public_ip_override}:${var.service_port}" : null
}

