terraform {
  required_version = "~> 1.13"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.2"
    }
  }
  backend "gcs" {
    prefix = "qa-pdftotext-service"
  }
}

provider "google" {
  project = var.gcp_project_id # default inherited by all resources
  region  = var.gcp_region     # default inherited by all resources
}

### service account ###

resource "google_service_account" "account" {
  account_id   = "qa-pdftotext-service"
  display_name = "Service account for the pdftotext service"
}

resource "google_project_iam_member" "ar_writer" {
  project = var.gcp_project_id
  role    = "roles/artifactregistry.createOnPushWriter"
  member  = "serviceAccount:${google_service_account.account.email}"
}

resource "google_project_iam_member" "cloud_run_admin" {
  project = var.gcp_project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.account.email}"
}

resource "google_project_iam_member" "logs_writer" {
  project = var.gcp_project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.account.email}"
}

resource "google_project_iam_member" "service_account_user" {
  project = var.gcp_project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${google_service_account.account.email}"
}

### cloud run instance ###

resource "google_cloud_run_v2_service" "pdftotext" {
  name     = "qa-pdftotext-service"
  location = "us-central1"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.account.email
    timeout         = "300s" # request timeout

    containers {
      image = var.image_path

      ports {
        container_port = 8888
      }

      # to use HTTP/2
      resources {
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "ENV"
        value = var.env
      }
      env {
        name  = "ACCEPTED_BUCKETS"
        value = var.accepted_buckets
      }
    }

    scaling {
      min_instance_count = 0 # default
    }
  }
}

### alerting ###

resource "google_monitoring_alert_policy" "cloud_run_error_alert" {
  display_name = "${google_cloud_run_v2_service.pdftotext.name} logging errors"
  combiner     = "OR"
  severity     = "ERROR"

  conditions {
    display_name = "Cloud Run error log"
    condition_matched_log {
      filter = "resource.type=\"cloud_run_revision\" AND severity=(\"ERROR\" OR \"CRITICAL\" OR \"ALERT\" OR \"EMERGENCY\") AND resource.labels.service_name=\"${google_cloud_run_v2_service.pdftotext.name}\""
    }
  }

  alert_strategy {
    notification_rate_limit {
      period = "300s" # limit notifications to every 5 minutes
    }
  }

  notification_channels = [
    "projects/${var.gcp_project_id}/notificationChannels/${var.slack_channel_id}"
  ]

  documentation {
    content   = "Cloud Run service ${google_cloud_run_v2_service.pdftotext.name} has reported an error - see logs."
    mime_type = "text/markdown"
  }
}
