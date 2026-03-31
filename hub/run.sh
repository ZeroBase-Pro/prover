#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_NAME="hub"
CONTAINER_NAME="hub-container"

print_help() {
    echo -e "${BLUE}Docker Hub Container Management Script${NC}"
    echo ""
    echo "Usage: ./run.sh [action]"
    echo ""
    echo "Actions:"
    echo "  build     - Build Docker image"
    echo "  start [config] - Start container, optional config is the host config file path to mount (overrides src/config/hub.py in container), and can automatically set port mapping based on the file's port"
    echo "  restart   - Restart container"
    echo "  logs      - View container logs"
    echo "  logs-f    - Follow container logs (follow mode)"
    echo "  stop      - Stop container"
    echo "  rm        - Remove container"
    echo "  rmi       - Remove image"
    echo "  clean     - Clean all (stop container, remove container and image)"
    echo "  status    - View container status"
    echo "  shell     - Enter container shell"
    echo "  help      - Display help information"
    echo ""
}

check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Error: Docker service is not running, please start Docker first${NC}"
        exit 1
    fi
}

build_container() {
    echo -e "${BLUE}Building Docker image...${NC}"
    docker compose build
    echo -e "${GREEN}Image build completed!${NC}"
}

start_container() {
    local config_path=${2:-}
    local port="9000"
    local scheme="http"
    echo -e "${BLUE}Starting container...${NC}"

    if [ -z "${SSL_CERTFILE:-}" ] && [ -z "${SSL_KEYFILE:-}" ] && [ -f "./certs/tls.crt" ] && [ -f "./certs/tls.key" ]; then
        export SSL_CERTFILE="/app/certs/tls.crt"
        export SSL_KEYFILE="/app/certs/tls.key"
        scheme="https"
        echo -e "${YELLOW}TLS certificates detected in ./certs${NC}"
    elif [ -n "${SSL_CERTFILE:-}" ] && [ -n "${SSL_KEYFILE:-}" ]; then
        scheme="https"
    fi

    export REQUIRE_TLS="${REQUIRE_TLS:-true}"
    if [ "${REQUIRE_TLS}" != "false" ] && [ "${REQUIRE_TLS}" != "0" ] && [ "${scheme}" != "https" ]; then
        echo -e "${RED}TLS is required but no certificate pair is available${NC}"
        exit 1
    fi

    if [ -n "$config_path" ]; then
        if [ -f "$config_path" ]; then
            echo -e "${YELLOW}Using config file: ${config_path}${NC}"
            port=$(sed -nE 's/.*port[[:space:]]*=[[:space:]]*([0-9]+).*/\1/p' "$config_path" | head -n1)
            if [ -z "$port" ]; then
                port="9000"
                echo -e "${YELLOW}Failed to parse port, using default port 9000${NC}"
            else
                echo -e "${YELLOW}Parsed port: ${port}${NC}"
            fi
            export CONTAINER_PORT="$port"
            export HOST_PORT="$port"
            export HUB_CONFIG="$config_path"
            docker compose up -d
        else
            echo -e "${RED}Config file does not exist: $config_path${NC}, starting with default port."
            docker compose up -d
        fi
    else
        docker compose up -d
    fi

    echo -e "${GREEN}Container started successfully (if no errors)!${NC}"
    echo -e "${YELLOW}Container name: ${CONTAINER_NAME}${NC}"
    echo -e "${YELLOW}Service running at: ${scheme}://localhost:${port}${NC}"
}

restart_container() {
    echo -e "${BLUE}Restarting container...${NC}"
    docker compose restart
    echo -e "${GREEN}Container restarted successfully!${NC}"
}

view_logs() {
    echo -e "${BLUE}Viewing container logs...${NC}"
    docker compose logs --tail=100
}

view_logs_follow() {
    echo -e "${BLUE}Following container logs (press Ctrl+C to exit)...${NC}"
    docker compose logs -f
}

stop_container() {
    echo -e "${BLUE}Stopping container...${NC}"
    docker compose stop
    echo -e "${GREEN}Container stopped${NC}"
}

remove_container() {
    echo -e "${YELLOW}Removing container...${NC}"
    docker compose down
    echo -e "${GREEN}Container removed${NC}"
}

remove_image() {
    echo -e "${YELLOW}Removing image...${NC}"
    docker rmi $(docker images "${PROJECT_NAME}*" -q) 2>/dev/null || echo "No image found"
    echo -e "${GREEN}Image removal completed${NC}"
}

clean_all() {
    echo -e "${RED}Cleaning all Docker resources...${NC}"
    docker compose down -v --rmi all
    echo -e "${GREEN}Cleanup completed${NC}"
}

show_status() {
    echo -e "${BLUE}Container status:${NC}"
    docker compose ps
    echo ""
    echo -e "${BLUE}Detailed information:${NC}"
    docker ps -a --filter "name=${CONTAINER_NAME}"
}

enter_shell() {
    echo -e "${BLUE}Entering container shell...${NC}"
    docker exec -it ${CONTAINER_NAME} /bin/bash
}

main() {
    local action=${1:-help}
    
    check_docker
    
    case $action in
        build)
            build_container
            ;;
        start)
            start_container "$@"
            ;;
        restart)
            restart_container
            ;;
        logs)
            view_logs
            ;;
        logs-f)
            view_logs_follow
            ;;
        stop)
            stop_container
            ;;
        rm)
            remove_container
            ;;
        rmi)
            remove_image
            ;;
        clean)
            clean_all
            ;;
        status)
            show_status
            ;;
        shell)
            enter_shell
            ;;
        help|--help|-h)
            print_help
            ;;
        *)
            echo -e "${RED}Unknown action: $action${NC}"
            print_help
            exit 1
            ;;
    esac
}

main "$@"
