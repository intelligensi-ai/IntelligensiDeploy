variable "project_id" {
  description = "Nebius project identifier."
  type        = string
}

variable "folder_id" {
  description = "Nebius folder/account scope identifier."
  type        = string
  default     = ""
}

variable "api_token" {
  description = "Nebius API token placeholder. TODO: wire into real provider auth."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "Nebius region."
  type        = string
  default     = "eu-north1"
}

variable "zone" {
  description = "Nebius zone."
  type        = string
  default     = "eu-north1-a"
}

variable "instance_name" {
  description = "Name of the GPU VM."
  type        = string
  default     = "intelligensi-comfyui"
}

variable "gpu_shape" {
  description = "GPU-enabled VM/container shape placeholder."
  type        = string
  default     = "gpu-standard-1"
}

variable "disk_size_gb" {
  description = "Boot or data disk size in GB."
  type        = number
  default     = 200
}

variable "ssh_username" {
  description = "SSH user for the Nebius VM."
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key used for VM access."
  type        = string
}

variable "container_image" {
  description = "Default container image intended for the service runtime."
  type        = string
  default     = "intelligensi/comfyui-service:latest"
}

variable "service_port" {
  description = "Exposed ComfyUI service port."
  type        = number
  default     = 8188
}

variable "public_ip_override" {
  description = "Temporary manual public IP for early scaffolding until the Nebius provider resources are wired."
  type        = string
  default     = ""
}

