terraform {
  required_version = ">= 1.7.0"
}

variable "environment" {
  type    = string
  default = "development"
}

output "control_plane_environment" {
  value = var.environment
}

