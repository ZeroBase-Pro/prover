#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   sudo ./pull.sh [HOST_GRPC_PORT] [HOST_HTTP_PORT] [HUB_API]

HOST_GRPC_PORT="${1:-${HOST_GRPC_PORT:-50050}}"
HOST_HTTP_PORT="${2:-${HOST_HTTP_PORT:-50051}}"
HUB_API="${3:-${HUB_API:-}}"

VER="${VER:-v0.0.1}"
IMAGE="${IMAGE:-zer0base/node:${VER}}"
NAME="${NAME:-node-container}"

GRPC_PORT_IN=50050
HTTP_PORT_IN=50051

MODE="${MODE:-sample}"
GRPC_HOST="${GRPC_HOST:-0.0.0.0}"
FASTAPI_HOST="${FASTAPI_HOST:-0.0.0.0}"

echo "Pulling image: ${IMAGE}"
docker pull "${IMAGE}"

NET_NAME="prover-network"
if ! docker network ls --format '{{.Name}}' | grep -q "^${NET_NAME}\$"; then
  echo "Creating network: ${NET_NAME}"
  docker network create "${NET_NAME}" >/dev/null
fi

if docker ps -a --format '{{.Names}}' | grep -Eq "^${NAME}$"; then
  echo "Removing existing container: ${NAME}"
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
fi

# ---- Key: resolve the `src` directory relative to this script ----
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_SRC_DIR="${SELF_DIR}/src"

# Optional: check required directories exist before starting to avoid mounting empty dirs
for d in crypto_keys session_keys config; do
  if [[ ! -d "${HOST_SRC_DIR}/${d}" ]]; then
    echo "ERROR: Missing directory: ${HOST_SRC_DIR}/${d}" >&2
    exit 1
  fi
done
# If you want to strictly validate presence of __init__.py:
if [[ ! -f "${HOST_SRC_DIR}/config/__init__.py" ]]; then
  echo "ERROR: ${HOST_SRC_DIR}/config/__init__.py not found!" >&2
  exit 1
fi

HUB_ENVS=()
[[ -n "${HUB_API}" ]] && HUB_ENVS+=(-e "HUB_API=${HUB_API}")
[[ -n "${HUB_API_URL:-}" ]] && HUB_ENVS+=(-e "HUB_API_URL=${HUB_API_URL}")

echo "Starting container: ${NAME}"
docker run -d --name "${NAME}" \
  -p "${HOST_GRPC_PORT}:${GRPC_PORT_IN}" \
  -p "${HOST_HTTP_PORT}:${HTTP_PORT_IN}" \
  -e "MODE=${MODE}" \
  -e "GRPC_HOST=${GRPC_HOST}" \
  -e "GRPC_PORT=${GRPC_PORT_IN}" \
  -e "FASTAPI_HOST=${FASTAPI_HOST}" \
  -e "FASTAPI_PORT=${HTTP_PORT_IN}" \
  -e "PYTHONPATH=/app/src" \
  "${HUB_ENVS[@]}" \
  -v "${HOST_SRC_DIR}/crypto_keys:/app/src/crypto_keys:ro" \
  -v "${HOST_SRC_DIR}/session_keys:/app/src/session_keys:ro" \
  -v "${HOST_SRC_DIR}/config:/app/src/config:ro" \
  --network "${NET_NAME}" \
  --restart unless-stopped \
  "${IMAGE}"

echo "Started ${NAME} — gRPC ${HOST_GRPC_PORT}->${GRPC_PORT_IN}, HTTP ${HOST_HTTP_PORT}->${HTTP_PORT_IN}"
echo "HUB_API: ${HUB_API:-<not set>}"
echo "Logs:   docker logs -f ${NAME}"
echo "Stop:   docker rm -f ${NAME}"