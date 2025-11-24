# Input variables for Terraform scaffolding.

variable "region" {
  description = "Region for infrastructure provisioning."
  type        = string
  default     = "us-east-1"
}

variable "gpu_type" {
  description = "GPU instance type identifier (e.g., nvidia-a10)."
  type        = string
  default     = "nvidia-a10"
}

variable "disk_size" {
  description = "Disk size allocated to the GPU instance in GB."
  type        = number
  default     = 200
}

variable "instance_name" {
  description = "Logical name for the GPU instance."
  type        = string
  default     = "intelligensi-gpu"
}
