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

variable "vllm_upstream" {
  type    = string
  default = "vllm/vllm-openai:v0.6.6"
}

locals {
  project_dir   = abspath("${path.root}/..")
  tags          = var.image_tag == "latest" ? ["latest"] : [var.image_tag, "latest"]
  repo_reranker = var.registry != "" ? "${var.registry}/hybrid-rag-reranker" : "hybrid-rag-reranker"
  repo_vllm     = var.registry != "" ? "${var.registry}/hybrid-rag-vllm-openai" : "hybrid-rag-vllm-openai"
}

# Custom CrossEncoder sidecar
source "docker" "reranker" {
  build {
    path       = "${local.project_dir}/reranker"
    dockerfile = "Dockerfile"
  }
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=hybrid-rag-reranker",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

# Mirror pinned vLLM image for private registry / SBOM pinning
source "docker" "vllm" {
  image  = var.vllm_upstream
  commit = true
  changes = [
    "LABEL org.opencontainers.image.title=hybrid-rag-vllm-openai",
    "LABEL org.opencontainers.image.version=${var.image_tag}",
    "LABEL org.opencontainers.image.base.name=${var.vllm_upstream}",
    "LABEL org.opencontainers.image.vendor=hybrid-rag",
  ]
}

build {
  name    = "hybrid-rag-reranker"
  sources = ["source.docker.reranker"]

  post-processor "docker-tag" {
    repository = local.repo_reranker
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
  name    = "hybrid-rag-vllm-openai"
  sources = ["source.docker.vllm"]

  post-processor "docker-tag" {
    repository = local.repo_vllm
    tags       = local.tags
  }

  dynamic "post-processor" {
    for_each = var.push ? [1] : []
    content {
      post-processor "docker-push" {}
    }
  }
}
