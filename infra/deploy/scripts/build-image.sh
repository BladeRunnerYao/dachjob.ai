#!/usr/bin/env bash
set -euo pipefail

#
# Build and push a Docker image.
#
# Usage: build-image.sh <dockerfile> <context> <registry> <image-name> <tag> [build-args...]
#
# Example:
#   build-image.sh app/backend/Dockerfile . acr.example.azurecr.io api abc123
#   build-image.sh app/frontend/Dockerfile . gar.example.dev api abc123 NEXT_PUBLIC_API_BASE_URL=https://...
#

dockerfile="$1"; shift
context="$1"; shift
registry="$1"; shift
image_name="$1"; shift
tag="$1"; shift

image="${registry}/${image_name}:${tag}"
latest_image="${registry}/${image_name}:latest"

build_args=()
for arg in "$@"; do
  build_args+=("--build-arg" "${arg}")
done

docker buildx build \
  --platform linux/amd64 \
  --push \
  -f "${dockerfile}" \
  "${build_args[@]}" \
  -t "${image}" \
  -t "${latest_image}" \
  "${context}"

echo "::notice::Built and pushed ${image}"
echo "image=${image}" >> "${GITHUB_OUTPUT}"
