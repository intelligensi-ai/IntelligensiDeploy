resource "lambdalabs_instance" "gpu" {
  instance_type = var.gpu_type
  ssh_key       = var.ssh_key
  count         = var.instance_count
}

output "public_ips" {
  value = lambdalabs_instance.gpu[*].ip
}
