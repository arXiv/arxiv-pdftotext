variable "gcp_project_id" {
  description = "GCP Project ID corresponding to environment"
  type        = string
}

variable "gcp_region" {
  description = "GCP Region for resource deployments"
  type        = string
}

variable "env" {
  description = "Deployment environment - DEV or PROD"
  type        = string
}

variable "image_path" {
  description = "Path to the container image in Artifact Registry"
  type        = string
}

variable "accepted_buckets" {
  description = "Bucket to write to"
  type        = string
}

variable "slack_channel_id" {
  description = "Channel ID for slack notification channel resource"
  type        = string
}
