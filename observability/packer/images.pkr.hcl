# Mirror upstream observability images — pins match compose/docker-compose.yml.

packer {
  required_plugins {
    docker = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/docker"
    }
  }
}

variable "image_tag" {
  type    = string
  default = "dev"
}

variable "registry" {
  type    = string
  default = ""
}

variable "push" {
  type    = bool
  default = false
}

locals {
  tags = var.image_tag == "latest" ? ["latest"] : [var.image_tag, "latest"]
  images = {
    langfuse_postgres = {
      upstream = "postgres:16-alpine"
      name     = "hybrid-rag-langfuse-postgres"
    }
    langfuse = {
      upstream = "langfuse/langfuse:2"
      name     = "hybrid-rag-langfuse"
    }
    otel_collector = {
      upstream = "otel/opentelemetry-collector-contrib:0.96.0"
      name     = "hybrid-rag-otel-collector"
    }
    signoz_collector = {
      upstream = "signoz/signoz-otel-collector:0.88.12"
      name     = "hybrid-rag-signoz-otel-collector"
    }
  }
}

source "docker" "langfuse_postgres" {
  image  = local.images.langfuse_postgres.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.langfuse_postgres.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.langfuse_postgres.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "langfuse" {
  image  = local.images.langfuse.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.langfuse.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.langfuse.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "otel_collector" {
  image  = local.images.otel_collector.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.otel_collector.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.otel_collector.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "signoz_collector" {
  image  = local.images.signoz_collector.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.signoz_collector.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.signoz_collector.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

build {
  name    = "hybrid-rag-langfuse-postgres"
  sources = ["source.docker.langfuse_postgres"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.langfuse_postgres.name}" : local.images.langfuse_postgres.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-langfuse"
  sources = ["source.docker.langfuse"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.langfuse.name}" : local.images.langfuse.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-otel-collector"
  sources = ["source.docker.otel_collector"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.otel_collector.name}" : local.images.otel_collector.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-signoz-otel-collector"
  sources = ["source.docker.signoz_collector"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.signoz_collector.name}" : local.images.signoz_collector.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}
