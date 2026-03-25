variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "cloudboxd"
}

variable "environment" {
  description = "Environment (dev/prod)"
  type        = string
  default     = "dev"
}
