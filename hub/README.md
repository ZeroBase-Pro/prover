# Hub

Containerized hub service for coordinating ZeroBase prover nodes. The hub exposes HTTP/gRPC helpers for node discovery, task dispatch, and result routing, and ships with a simple Docker Compose wrapper so you can run it with one command.

## Project Layout

```
hub/
├── run.sh                # Wrapper for build/start/stop/logs
├── docker-compose.yml    # Compose service definition
├── Dockerfile            # Image build instructions
└── src/                  # Application code and runtime assets
    ├── main.py           # Sanic/uvicorn entrypoint
    ├── config/           # Hub configuration (hub.py is the default)
    ├── crypto_keys/      # Placeholder for crypto material (mounted into the container)
    ├── session_keys/     # Session keypair (private_key/public_key)
    └── ...               # API, modules, middleware, utils
```

## Before you begin

This repository is intended to run on a server-grade machine with a Trusted Execution Environment (TEE) and a public IP (or properly configured NAT/port forwarding). Running the services on consumer/home devices or laptops is not recommended.

- **Why:** The hub and proving services expect external connectivity and may require public IP mapping for gRPC/HTTP endpoints and inter-service communication.
- **What to use:** A TEE-capable server or cloud instance with TEE support and a static/public IP address.

## Prerequisites

- Docker and Docker Compose installed; ability to run `sudo docker ...`.
- Network Access: Inbound access must be allowed on the chosen hub port (default: `9000`) for prover nodes to connect.
- Configuration: update `src/config/hub.py` (or prepare your own config file with the same `Config` structure). The hub port is read from `Server.Sanic.port`. If you pass a custom config to `run.sh start`, the script will parse that port automatically.
- Keys: place `private_key` and `public_key` inside `src/session_keys/`. You can generate a pair with `python -m src.utils.cli init_keys --path src/session_keys`.
- Optional: add any required materials under `src/crypto_keys/` if your deployment relies on them.

Minimal config shape (`src/config/hub.py`):

```python
class Config:
    class Env:
        app = "zerobase-hub"
        debug = False
        logs_path = "src/logs"
        crypto_keys_path = "src/crypto_keys"
        session_keys_path = "src/session_keys"

    class Server:
        class Sanic:
            host = "0.0.0.0"
            port = YOUR_DESIRED_PORT_NUMBER  # e.g., 9000
            forwarded_secret = "ABCDEFG"
            real_ip_header = "cf-connecting-ip"
            proxies_count = 2
            cors_domains = ['*']

    class Explorer:
        api = "YOUR_EXPLORER_API_URL"
        key_path = "YOUR_EXPLORER_API_KEY_PATH"
```

## Quick Start

Pick the run mode that matches your setup (all commands from repo root):

```bash
# 1) Start with in-repo config (uses src/config/hub.py, default port 9000)
sudo ./run.sh start

# 2) Start with a custom config file (port is parsed from the file)
sudo ./run.sh start ./configs/local_hub.py
```

The script sets `HOST_PORT`/`CONTAINER_PORT` using the first `port = <number>` it finds in the provided config and mounts that file into the container as `/app/src/config/hub.py`. If parsing fails, it falls back to port `9000`.

## Managing the Container

`run.sh` drives Docker Compose. Useful actions:

- `sudo ./run.sh start [config_path]` start (or create) the hub container.
- `sudo ./run.sh restart` restart the running container.
- `sudo ./run.sh logs` view recent logs; `logs-f` to follow.
- `sudo ./run.sh stop` stop the container; `rm` removes it; `rmi` removes images; `clean` wipes everything.
- `sudo ./run.sh status` check compose status; `shell` enters the container shell.

Under the hood, Compose brings up a single service `hub` (container `hub-container`) on the `prover-network` bridge. You can also use plain Compose commands, e.g. `docker compose ps` or `docker compose logs -f hub`.

## Verify It’s Running

- Check containers: `sudo docker compose ps`
- Tail logs: `sudo docker compose logs -f hub`
- Reachability: open `http://localhost:9000` (or your configured port) from a node or via `curl` to confirm the listener is up.

Deploy notes:
- Keep your config and key files present on the host; they are mounted read-only into the container.
- If you use an alternate config file, make sure it is accessible to Docker (absolute or repo-relative path).
