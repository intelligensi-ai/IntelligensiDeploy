variable "gpu_type" {
  description = "Identifier for the GPU instance type."
  type        = string
}

variable "disk_size" {
  description = "Disk size allocated to the instance in GB."
  type        = number
}

variable "region" {
  description = "Region used to contextualize the instance metadata."
  type        = string
}

variable "instance_name" {
  description = "Human readable name for the GPU instance."
  type        = string
}
