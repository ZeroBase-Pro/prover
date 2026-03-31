#!/usr/bin/env bash
set -euo pipefail

HOST_GRPC_PORT="${1:-${HOST_GRPC_PORT:-50050}}"
HOST_HTTP_PORT="${2:-${HOST_HTTP_PORT:-50051}}"
HUB_API="${3:-${HUB_API:-}}"

VER="${VER:-v0.0.1}"
IMAGE="${IMAGE:-zer0base/node:${VER}}"
NAME="${NAME:-node-container}"

GRPC_PORT_IN=50050
HTTP_PORT_IN=50051

MODE="${MODE:-NODE}"
GRPC_HOST="${GRPC_HOST:-0.0.0.0}"
FASTAPI_HOST="${FASTAPI_HOST:-0.0.0.0}"
REQUIRE_TLS="${REQUIRE_TLS:-true}"

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

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_SRC_DIR="${SELF_DIR}/src"

for d in crypto_keys session_keys config; do
  if [[ ! -d "${HOST_SRC_DIR}/${d}" ]]; then
    echo "ERROR: Missing directory: ${HOST_SRC_DIR}/${d}" >&2
    exit 1
  fi
done

if [[ ! -f "${HOST_SRC_DIR}/config/__init__.py" ]]; then
  echo "ERROR: ${HOST_SRC_DIR}/config/__init__.py not found!" >&2
  exit 1
fi

HOST_CERT_DIR="${SELF_DIR}/certs"
if [[ -z "${SSL_CERTFILE:-}" && -z "${SSL_KEYFILE:-}" && -f "${HOST_CERT_DIR}/tls.crt" && -f "${HOST_CERT_DIR}/tls.key" ]]; then
  SSL_CERTFILE="/app/certs/tls.crt"
  SSL_KEYFILE="/app/certs/tls.key"
fi

if [[ "${REQUIRE_TLS}" != "false" && "${REQUIRE_TLS}" != "0" ]]; then
  if [[ ! -f "${HOST_CERT_DIR}/tls.crt" || ! -f "${HOST_CERT_DIR}/tls.key" ]]; then
    echo "ERROR: TLS is required but certs/tls.crt or certs/tls.key is missing." >&2
    exit 1
  fi
fi

if [[ -z "${HUB_API}" ]]; then
  NODE_PY="${HOST_SRC_DIR}/config/node.py"

  if command -v python3 >/dev/null 2>&1; then
    HUB_API="$(python3 - <<PY 2>/dev/null || true
import sys
sys.path.insert(0, "${HOST_SRC_DIR}")
from config.node import Config
print(getattr(getattr(getattr(Config, "Hub"), "API"), "url"))
PY
)"
  fi

  if [[ -z "${HUB_API}" && -f "${NODE_PY}" ]]; then
    HUB_API="$(grep -E '^[[:space:]]*url[[:space:]]*=' "${NODE_PY}" \
      | head -n1 \
      | sed -E 's/.*=[[:space:]]*["'"'"']?([^"'"'"'#]+).*/\1/' \
      || true)"
  fi

  if [[ -n "${HUB_API}" ]]; then
    echo "HUB_API not provided; using value from node.py: ${HUB_API}"
  else
    echo "WARNING: HUB_API not provided and could not be read from node.py; leaving HUB_API unset." >&2
  fi
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
  -e "REQUIRE_TLS=${REQUIRE_TLS}" \
  -e "SSL_CERTFILE=${SSL_CERTFILE:-}" \
  -e "SSL_KEYFILE=${SSL_KEYFILE:-}" \
  -e "VERIFY_HUB_TLS=${VERIFY_HUB_TLS:-false}" \
  -e "VERIFY_PROVER_TLS=${VERIFY_PROVER_TLS:-false}" \
  -e "NODE_REGISTER_TOKEN=${NODE_REGISTER_TOKEN:-}" \
  -e "PYTHONPATH=/app/src" \
  "${HUB_ENVS[@]}" \
  -v "${HOST_SRC_DIR}/crypto_keys:/app/src/crypto_keys:ro" \
  -v "${HOST_SRC_DIR}/session_keys:/app/src/session_keys:ro" \
  -v "${HOST_SRC_DIR}/config:/app/src/config:ro" \
  -v "${HOST_CERT_DIR}:/app/certs:ro" \
  --network "${NET_NAME}" \
  --restart unless-stopped \
  "${IMAGE}"

echo "Started ${NAME} — gRPC ${HOST_GRPC_PORT}->${GRPC_PORT_IN}, HTTP ${HOST_HTTP_PORT}->${HTTP_PORT_IN}"
echo "HUB_API: ${HUB_API:-<not set>}"
echo "Logs:   docker logs -f ${NAME}"
echo "Stop:   docker rm -f ${NAME}"
