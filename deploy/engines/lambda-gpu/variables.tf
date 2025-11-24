variable "lamda_api_key" {
  type        = string
  description = "LambdaLabs API Key"
}

variable "gpu_type" {
  type    = string
  default = "gpu_1x_a10"
}

variable "ssh_key" {
  type        = string
  description = "Contents of your SSH public key"
}

variable "instance_count" {
  type    = number
  default = 1
}
