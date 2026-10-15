# ═══════════════════════════════════════════════════════
# FaMTNarriAI — Terraform IaC
# Provisions the Kubernetes deployment using Terraform
# instead of running kubectl apply manually
# ═══════════════════════════════════════════════════════

terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}

# Connect to your local Minikube cluster
provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = "minikube"
}

# ── Deployment ──────────────────────────────────────────
resource "kubernetes_deployment" "famtnarriai" {
  metadata {
    name = "famtnarriai"
    labels = {
      app = "famtnarriai"
    }
  }

  spec {
    replicas = 2

    selector {
      match_labels = {
        app = "famtnarriai"
      }
    }

    template {
      metadata {
        labels = {
          app = "famtnarriai"
        }
      }

      spec {
        container {
          name  = "famtnarriai"
          image = "ghcr.io/mikemesfintadesse/famtnarriai:latest"

          port {
            container_port = 8000
          }

          resources {
            requests = {
              memory = "256Mi"
              cpu    = "250m"
            }
            limits = {
              memory = "512Mi"
              cpu    = "500m"
            }
          }
        }
      }
    }
  }
}

# ── Service ─────────────────────────────────────────────
resource "kubernetes_service" "famtnarriai" {
  metadata {
    name = "famtnarriai-service"
  }

  spec {
    selector = {
      app = "famtnarriai"
    }

    port {
      port        = 80
      target_port = 8000
    }

    type = "NodePort"
  }
}
