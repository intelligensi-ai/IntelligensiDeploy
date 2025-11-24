output "public_ips" {
  description = "Public IPs for provisioned GPU nodes"
  value       = module.gpu.public_ips
}
