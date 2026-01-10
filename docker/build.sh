#!/bin/bash
# Build and push custom Docker images to Docker Hub
#
# Prerequisites:
# 1. Docker installed
# 2. Docker Hub account (docker login)
# 3. Run on Linux with NVIDIA GPU (for CUDA compatibility)
#
# Usage:
#   ./build.sh comfyui    # Build ComfyUI image
#   ./build.sh swarmui    # Build SwarmUI image
#   ./build.sh all        # Build both

set -e

# Change this to your Docker Hub username
DOCKER_USER="${DOCKER_USER:-yourusername}"
VERSION="${VERSION:-latest}"

build_comfyui() {
    echo "Building ComfyUI image..."
    docker build \
        -t ${DOCKER_USER}/comfyui-i2v:${VERSION} \
        -f Dockerfile.comfyui \
        .

    echo "Pushing to Docker Hub..."
    docker push ${DOCKER_USER}/comfyui-i2v:${VERSION}

    echo "Done! Use this image in vast.ai:"
    echo "  ${DOCKER_USER}/comfyui-i2v:${VERSION}"
}

build_swarmui() {
    echo "Building SwarmUI image..."
    docker build \
        -t ${DOCKER_USER}/swarmui-i2v:${VERSION} \
        -f Dockerfile.swarmui \
        .

    echo "Pushing to Docker Hub..."
    docker push ${DOCKER_USER}/swarmui-i2v:${VERSION}

    echo "Done! Use this image in vast.ai:"
    echo "  ${DOCKER_USER}/swarmui-i2v:${VERSION}"
}

case "$1" in
    comfyui)
        build_comfyui
        ;;
    swarmui)
        build_swarmui
        ;;
    all)
        build_comfyui
        build_swarmui
        ;;
    *)
        echo "Usage: $0 {comfyui|swarmui|all}"
        echo ""
        echo "Environment variables:"
        echo "  DOCKER_USER  - Docker Hub username (required)"
        echo "  VERSION      - Image tag (default: latest)"
        echo ""
        echo "Example:"
        echo "  DOCKER_USER=myusername ./build.sh comfyui"
        exit 1
        ;;
esac
