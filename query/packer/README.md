# Packer — hybrid-rag-query

Builds `hybrid-rag-query:${image_tag}` from the project `Dockerfile`.

```bash
make packer-build IMAGE_TAG=query-v1.0.0
# or
packer init packer && packer build -var 'image_tag=dev' packer/
```

See [../../packer/README.md](../../packer/README.md) for registry push and build-all.
