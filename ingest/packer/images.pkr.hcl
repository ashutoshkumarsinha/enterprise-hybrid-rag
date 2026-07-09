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
  project_dir = abspath("${path.root}/..")
  tags        = var.image_tag == "latest" ? ["latest"] : [var.image_tag, "latest"]
  repo_orchestrator = var.registry != "" ? "${var.registry}/hybrid-rag-ingest-orchestrator" : "hybrid-rag-ingest-orchestrator"
  repo_worker       = var.registry != "" ? "${var.registry}/hybrid-rag-ingest-worker" : "hybrid-rag-ingest-worker"
}

source "docker" "orchestrator" {
  build {
    path       = local.project_dir
    dockerfile = "Dockerfile"
  }
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=hybrid-rag-ingest-orchestrator",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

source "docker" "worker" {
  build {
    path       = local.project_dir
    dockerfile = "Dockerfile.worker"
  }
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=hybrid-rag-ingest-worker",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

build {
  name = "hybrid-rag-ingest-orchestrator"
  sources = ["source.docker.orchestrator"]

  post-processor "docker-tag" {
    repository = local.repo_orchestrator
    tags       = local.tags
  }

  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content {
      post-processor "docker-push" {}
    }
  }
}

build {
  name = "hybrid-rag-ingest-worker"
  sources = ["source.docker.worker"]

  post-processor "docker-tag" {
    repository = local.repo_worker
    tags       = local.tags
  }

  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content {
      post-processor "docker-push" {}
    }
  }
}
