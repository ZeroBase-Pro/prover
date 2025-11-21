#!/usr/bin/env bash
set -euo pipefail

# Usage: sudo ./pull.sh [cpu|gpu] [HOST_PORT]
VER="${VER:-v0.0.1}" 
MODE="${1:-gpu}"
MODE="$(echo "$MODE" | tr 'A-Z' 'a-z')"

# Port: prioritize 2nd parameter, then HOST_PORT env var, default 60050
HOST_PORT="${2:-${HOST_PORT:-60050}}"
CONTAINER_PORT=60050

NET_NAME="prover-network"
if ! docker network ls --format '{{.Name}}' | grep -q "^${NET_NAME}\$"; then
  echo "Creating network: ${NET_NAME}"
  docker network create "${NET_NAME}" >/dev/null
fi

case "$MODE" in
  gpu)
    IMAGE="${IMAGE:-zer0base/gnark-prover:gpu-${VER}}"
    NAME="${NAME:-gnark-prover}"
    ;;
  cpu)
    IMAGE="${IMAGE:-zer0base/gnark-prover:cpu-${VER}}"
    NAME="${NAME:-gnark-prover}"
    ;;
  *)
    echo "Usage: $0 [cpu|gpu] [HOST_PORT]" >&2
    exit 1
    ;;
esac

echo "Pulling image: ${IMAGE}"
docker pull "${IMAGE}"

# If container with same name exists, delete it first
if docker ps -a --format '{{.Names}}' | grep -Eq "^${NAME}$"; then
  echo "Removing existing container: ${NAME}"
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
fi

echo "Starting container: ${NAME}"
if [[ "$MODE" == "gpu" ]]; then
  docker run -d --name "${NAME}" \
    --gpus all \
    --network prover-network \
    -p "${HOST_PORT}:${CONTAINER_PORT}" \
    -e "PORT=${CONTAINER_PORT}" \
    -e TEMPLATE_DIR=./template \
    -e "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}" \
    -e "NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}" \
    -e "NVIDIA_DRIVER_CAPABILITIES=${NVIDIA_DRIVER_CAPABILITIES:-compute,utility}" \
    -e "ICICLE_BACKEND_INSTALL_DIR=/usr/local/lib/backend" \
    --restart unless-stopped \
    "${IMAGE}"
else
  docker run -d --name "${NAME}" \
    --network prover-network \
    -p "${HOST_PORT}:${CONTAINER_PORT}" \
    -e "PORT=${CONTAINER_PORT}" \
    -e TEMPLATE_DIR=./template \
    --restart unless-stopped \
    "${IMAGE}"
fi

echo "Started ${NAME} (${MODE}) — ${HOST_PORT} -> ${CONTAINER_PORT}"
echo "Logs:   docker logs -f ${NAME}"
echo "Stop:   docker rm -f ${NAME}"