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
  repo_name   = var.registry != "" ? "${var.registry}/hybrid-rag-query" : "hybrid-rag-query"
  tags        = var.image_tag == "latest" ? ["latest"] : [var.image_tag, "latest"]
}

source "docker" "query" {
  build {
    path       = local.project_dir
    dockerfile = "Dockerfile"
  }
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=hybrid-rag-query",
    "LABEL org.opencontainers.image.description=Enterprise Hybrid RAG MCP and query gateway",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

build {
  name    = "hybrid-rag-query"
  sources = ["source.docker.query"]

  post-processor "docker-tag" {
    repository = local.repo_name
    tags       = local.tags
  }

  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content {
      post-processor "docker-push" {}
    }
  }
}
