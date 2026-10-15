output "service_name" {
  value = kubernetes_service.famtnarriai.metadata[0].name
}

output "replicas" {
  value = kubernetes_deployment.famtnarriai.spec[0].replicas
}
