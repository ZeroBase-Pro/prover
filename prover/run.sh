#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ZeroBase Docker Prover -Orchestration Script
# =============================================================================
# Two usages are supported:
# 1) Recommended flags form:
#    sudo ./run.sh --mode gpu \
#                  --node-grpc 50050 --node-http 50051 \
#                  --circom-port 60051 --gnark-port 60050 \
#                  --hub http://127.0.0.1:9000
#    (If you need to specify separately: --circom-mode cpu --gnark-mode gpu)
#
# 2) Compatible with the old "port by location":
#    sudo ./run.sh [cpu|gpu] [node_grpc] [node_http] [circom_port] [gnark_port] [hub_api]
#    example: sudo ./run.sh gpu 50050 50051 60051 60050 http://127.0.0.1:9000
# =============================================================================

print_usage() {
  cat <<EOF
Usage:
  $(basename "$0") [--mode cpu|gpu] [--circom-mode cpu|gpu] [--gnark-mode cpu|gpu]
                   [--node-grpc PORT] [--node-http PORT]
                   [--circom-port PORT] [--gnark-port PORT]
                   [--hub URL]

Examples:
  $(basename "$0") --mode gpu --node-grpc 50050 --node-http 50051 --circom-port 60051 --gnark-port 60050 --hub http://127.0.0.1:9000
  $(basename "$0") gpu 50050 50051 60051 60050 http://127.0.0.1:9000
EOF
}

GLOBAL_MODE="${MODE:-gpu}"    
CIRCOM_MODE="$GLOBAL_MODE"
GNARK_MODE="$GLOBAL_MODE"

NODE_GRPC_PORT=50050
NODE_HTTP_PORT=50051
CIRCOM_PORT=60051
GNARK_PORT=60050
HUB_API=""

is_number() { [[ "${1:-}" =~ ^[0-9]+$ ]]; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)          GLOBAL_MODE="$2"; CIRCOM_MODE="$2"; GNARK_MODE="$2"; shift 2;;
    --circom-mode)   CIRCOM_MODE="$2"; shift 2;;
    --gnark-mode)    GNARK_MODE="$2"; shift 2;;
    --node-grpc)     NODE_GRPC_PORT="$2"; shift 2;;
    --node-http)     NODE_HTTP_PORT="$2"; shift 2;;
    --circom-port)   CIRCOM_PORT="$2"; shift 2;;
    --gnark-port)    GNARK_PORT="$2"; shift 2;;
    --hub|--hub-api) HUB_API="${2:-}"; shift 2;;
    -h|--help)       print_usage; exit 0;;
    cpu|gpu)
      GLOBAL_MODE="$1"; CIRCOM_MODE="$1"; GNARK_MODE="$1"; shift
      ;;
    *)
      if is_number "$1"; then
        NODE_GRPC_PORT="$1"; shift
        if [[ $# -gt 0 && "$(is_number "${1:-}" && echo yes)" == "yes" ]]; then NODE_HTTP_PORT="$1"; shift; fi
        if [[ $# -gt 0 && "$(is_number "${1:-}" && echo yes)" == "yes" ]]; then CIRCOM_PORT="$1"; shift; fi
        if [[ $# -gt 0 && "$(is_number "${1:-}" && echo yes)" == "yes" ]]; then GNARK_PORT="$1"; shift; fi
        if [[ $# -gt 0 ]]; then HUB_API="$1"; shift; fi
      else
        echo "Unknown argument: $1"; print_usage; exit 1
      fi
      ;;
  esac
done

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}ZeroBase Docker Prover - Starting Services${NC}"
echo -e "Circom mode: ${GREEN}${CIRCOM_MODE}${NC}, Gnark mode: ${GREEN}${GNARK_MODE}${NC}"
echo -e "Node gRPC/HTTP: ${GREEN}${NODE_GRPC_PORT}/${NODE_HTTP_PORT}${NC}, Circom: ${GREEN}${CIRCOM_PORT}${NC}, Gnark: ${GREEN}${GNARK_PORT}${NC}"
[[ -n "${HUB_API}" ]] && echo -e "Hub API: ${GREEN}${HUB_API}${NC}"

if [[ $EUID -ne 0 ]]; then
  echo -e "${YELLOW}Warning: run with sudo for Docker if needed.${NC}" >&2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "\n${YELLOW}Starting Node Service...${NC}"
bash "./node/pull.sh" "${NODE_GRPC_PORT}" "${NODE_HTTP_PORT}" "${HUB_API}"

echo -e "\n${YELLOW}Starting Circom Prover...${NC}"
bash "./circom-prover/pull.sh" "${CIRCOM_MODE}" "${CIRCOM_PORT}"

echo -e "\n${YELLOW}Starting Gnark Prover...${NC}"
bash "./gnark-prover/pull.sh" "${GNARK_MODE}" "${GNARK_PORT}"

echo -e "\n${GREEN}All services started! 🚀${NC}"
echo -e "Node:   localhost:${NODE_GRPC_PORT} (gRPC), localhost:${NODE_HTTP_PORT} (HTTP)"
echo -e "Circom: localhost:${CIRCOM_PORT}"
echo -e "Gnark:  localhost:${GNARK_PORT}"