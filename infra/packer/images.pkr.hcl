# Mirror upstream store images with hybrid-rag labels and registry-friendly names.
# No custom Dockerfile in infra — pins match compose/docker-compose.yml.

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
    qdrant = {
      upstream = "qdrant/qdrant:v1.12.5"
      name     = "hybrid-rag-qdrant"
    }
    neo4j = {
      upstream = "neo4j:5.26-community"
      name     = "hybrid-rag-neo4j"
    }
    redis = {
      upstream = "redis:7-alpine"
      name     = "hybrid-rag-redis"
    }
    minio = {
      upstream = "minio/minio:RELEASE.2024-12-18T13-15-44Z"
      name     = "hybrid-rag-minio"
    }
    postgres = {
      upstream = "postgres:16-alpine"
      name     = "hybrid-rag-postgres"
    }
    caddy = {
      upstream = "caddy:2.8-alpine"
      name     = "hybrid-rag-caddy"
    }
    keycloak = {
      upstream = "quay.io/keycloak/keycloak:26.0"
      name     = "hybrid-rag-keycloak"
    }
  }
}

# Generate one source block per mirrored image
source "docker" "qdrant" {
  image  = local.images.qdrant.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.qdrant.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.qdrant.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "neo4j" {
  image  = local.images.neo4j.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.neo4j.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.neo4j.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "redis" {
  image  = local.images.redis.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.redis.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.redis.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "minio" {
  image  = local.images.minio.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.minio.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.minio.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "postgres" {
  image  = local.images.postgres.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.postgres.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.postgres.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "caddy" {
  image  = local.images.caddy.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.caddy.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.caddy.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "keycloak" {
  image  = local.images.keycloak.upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=${local.images.keycloak.name}",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${local.images.keycloak.upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

build {
  name    = "hybrid-rag-qdrant"
  sources = ["source.docker.qdrant"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.qdrant.name}" : local.images.qdrant.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-neo4j"
  sources = ["source.docker.neo4j"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.neo4j.name}" : local.images.neo4j.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-redis"
  sources = ["source.docker.redis"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.redis.name}" : local.images.redis.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-minio"
  sources = ["source.docker.minio"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.minio.name}" : local.images.minio.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-postgres"
  sources = ["source.docker.postgres"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.postgres.name}" : local.images.postgres.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-caddy"
  sources = ["source.docker.caddy"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.caddy.name}" : local.images.caddy.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}

build {
  name    = "hybrid-rag-keycloak"
  sources = ["source.docker.keycloak"]
  post-processor "docker-tag" {
    repository = var.registry != "" ? "${var.registry}/${local.images.keycloak.name}" : local.images.keycloak.name
    tags       = local.tags
  }
  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content { post-processor "docker-push" {} }
  }
}
