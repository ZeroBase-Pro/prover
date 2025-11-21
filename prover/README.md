# Prover

Dockerized distribution for zero knowledge proof services. This repository bundles three services with consistent deployment and observability:

- **Node Service**: API gateway service that orchestrates and routes requests to proving services.
- **Circom Prover**: a service for proving Circom circuits.
- **Gnark Prover**: a service for proving Gnark circuits.

All services expose a gRPC interface and support CPU and NVIDIA GPU runtime modes.

## Project layout

```
prover/
├── node/                 # Node API gateway service
│   ├── src/              # Service sources and configurations
│   │   ├── crypto_keys/  # Cryptographic keys
│   │   ├── session_keys/ # Session keys
│   │   └── config/       # Configuration files
│   └── pull.sh           # Deployment helper script
├── circom-prover/        # Circom proving service
│   ├── src_cpu/          # CPU entrypoint
│   ├── src_gpu/          # GPU entrypoint
│   ├── src/              # Service sources and gRPC definitions
│   ├── lib/              # Shared library code
│   ├── pull.sh           # Deployment helper script
│   └── go.mod            # Go module
├── gnark-prover/         # Gnark proving service
│   ├── src_cpu/          # CPU entrypoint
│   ├── src_gpu/          # GPU entrypoint
│   ├── src/              # Service sources and gRPC definitions
│   ├── pull.sh           # Deployment helper script
│   └── go.mod            # Go module
├── run.sh                # Integrated orchestration script
└── README.md             # This document
```

## Before you begin

### Deployment environment

This repository is intended to run on a server-grade machine with a Trusted Execution Environment (TEE) and a public IP (or properly configured NAT/port forwarding). Running the services on consumer/home devices or laptops is not recommended.

- Why: the proving services expect external connectivity and may require public IP mapping for gRPC/HTTP endpoints and inter-service communication.
- What to use: a TEE-capable server or cloud instance with TEE support and a static/public IP address.

### Required pre-start checklist

These items are required for the Node service and will cause scripts/containers to fail if missing. Complete them before you run `run.sh` or any `pull.sh`.

- Populate `node/src/config/` with your environment-specific configuration. At minimum, copy or edit the provided `sample.py`, then rename it to `node.py` to make it the active config. Ensure that `node/src/config/__init__.py` exposes the active configuration.
- Place the correct `public_key` file at `node/src/session_keys/public_key`. If this key is missing or incorrect the Node service will not be able to validate sessions.
- Note: the Node container runs with `PYTHONPATH=/app/src` and the `node/pull.sh` will mount `node/src` into the container as read-only. Missing files or empty mounts commonly cause immediate container failures.

### System prerequisites and performance

Before deploying, ensure your system meets the following prerequisites and performance expectations. These are shown here so they're reviewed before the Quick Start commands.

#### Prerequisites

- Docker and Docker Compose installed (latest versions recommended).
- Permissions to pull images and run containers (root or membership in the `docker` group).
- Internet access to pull images and dependencies.

CPU-only: no additional requirements.

GPU (NVIDIA) mode:
- NVIDIA graphics driver that supports CUDA 12.x (driver 535+ recommended).
  See: https://docs.nvidia.com/deploy/cuda-compatibility/index.html
- NVIDIA Container Toolkit installed. ICICLE targets CUDA Toolkit ≥12.0; older CUDA versions may work but are not officially supported.

#### Performance considerations

- Hardware: any compatible CPU or NVIDIA GPU.
- CUDA: ICICLE targets CUDA Toolkit ≥ 12.0. GPUs supporting only CUDA 11 may still work but aren't officially supported.
- GPU memory (VRAM): depends on circuit size and proving key. 8 GB+ is recommended for small circuits; 16 GB+ advisable for medium–large circuits.

## Quick Start

Usage examples (pick the one that fits your environment):

```bash
# 1) Default (GPU) — recommended for machines with NVIDIA GPU and correct drivers/toolkit
sudo ./run.sh

# 2) Explicit GPU mode with explicit ports
sudo ./run.sh --mode gpu --node-grpc 50050 --node-http 50051 --circom-port 60051 --gnark-port 60050 --hub http://localhost:9000

# 3) CPU-only run (useful for CI or machines without GPU)
sudo ./run.sh --mode cpu --node-grpc 50050 --node-http 50051 --circom-port 60051 --gnark-port 60050

# 4) Mixed modes: run Circom on CPU and Gnark on GPU
sudo ./run.sh --mode gpu --circom-mode cpu --gnark-mode gpu --node-grpc 50050 --node-http 50051 --circom-port 60051 --gnark-port 60050

# 5) Backwards-compatible positional form
sudo ./run.sh gpu 50050 50051 60051 60050 http://localhost:9000
```

This will start:
- **Node Service**: API gateway (gRPC: 50050, HTTP: 50051)
- **Circom Prover**: Circom proving service (60051)
- **Gnark Prover**: Gnark proving service (60050)

## Individual Service Deployment

If you prefer to start services individually, each subfolder contains a `pull.sh` that pulls the official image and runs a container. Below are the accurate usages and notes extracted from the actual scripts.

1) **Node Service (`node/pull.sh`)**

```bash
cd node
sudo ./pull.sh [HOST_GRPC_PORT] [HOST_HTTP_PORT] [HUB_API]
# Example: sudo ./pull.sh 50050 50051 http://localhost:9000
```

Notes for `node/pull.sh`:
- Default ports: gRPC `50050`, HTTP `50051` (these are the container ports the script exposes).
- The script mounts the repository's `node/src` subdirectories into the container. It expects the following directories to exist in the host `node/src` directory before running:
  - `crypto_keys`
  - `session_keys`
  - `config` (and `config/__init__.py`)
- If any of the above are missing, the script will fail with an error; this is a deliberate safety check to avoid launching a container with an empty or incomplete mount.
- See the "Required pre-start checklist" above for the required `config/`, `.env` and `session_keys/public_key` setup. These items must be completed before running any `pull.sh` or `run.sh` script.
- The script sets `PYTHONPATH=/app/src` inside the container and will pass optional `HUB_API`/`HUB_API_URL` environment variables when provided.

2) **Circom Prover (`circom-prover/pull.sh`)**

```bash
cd circom-prover
sudo ./pull.sh [mode] [HOST_PORT]
# mode: cpu|gpu (default: gpu)
# HOST_PORT defaults to 60051 when not provided or via HOST_PORT env var
# Example: sudo ./pull.sh gpu 60051
```

Notes for `circom-prover/pull.sh`:
- Default mode: `gpu`.
- Default host port: `60051` (container port `60051`).
- Environment variables supported (examples): `IMAGE`, `NAME`, `HOST_PORT`, `CUDA_VISIBLE_DEVICES`, `NVIDIA_VISIBLE_DEVICES`, `NVIDIA_DRIVER_CAPABILITIES`, `ICICLE_BACKEND_INSTALL_DIR`, `TEMPLATE_DIR`.
- The script will create a Docker network named `prover-network` if it does not already exist.

3) **Gnark Prover (`gnark-prover/pull.sh`)**

```bash
cd gnark-prover
sudo ./pull.sh [mode] [HOST_PORT]
# mode: cpu|gpu (default: gpu)
# HOST_PORT defaults to 60050 when not provided or via HOST_PORT env var
# Example: sudo ./pull.sh gpu 60050
```

Notes for `gnark-prover/pull.sh`:
- Default mode: `gpu`.
- Default host port: `60050` (container port `60050`).
- Same environment variables pattern as `circom-prover` (e.g. `IMAGE`, `NAME`, `CUDA_VISIBLE_DEVICES`).
- The script will also create/use Docker network `prover-network`.



## Verify Service Operation

```bash
# Check container status
sudo docker ps

# Test service connectivity (replace ports if you started services on custom ports)
telnet localhost 50050  # Node Service (gRPC)
telnet localhost 50051  # Node Service (HTTP)
telnet localhost 60051  # Circom Prover
telnet localhost 60050  # Gnark Prover

# View service logs (container names are configurable through env IMAGE/NAME; defaults below)
sudo docker logs -f node-container      # default NAME in node/pull.sh
sudo docker logs -f circom-prover       # default NAME in circom-prover/pull.sh
sudo docker logs -f gnark-prover        # default NAME in gnark-prover/pull.sh

# Common container lifecycle operations
sudo docker stop <container>

# Start a container
sudo docker start <container>

# Restart a container
sudo docker restart <container>

# Pause / unpause a container
sudo docker pause <container>
sudo docker unpause <container>
```

## Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                               Prover                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   Node Service  │    │ Circom Prover   │    │ Gnark Prover    │ │
│  │   (Gateway)     │    │   (CPU/GPU)     │    │   (CPU/GPU)     │ │
│  │                 │    │                 │    │                 │ │
│  │ gRPC: 50050     │    │ gRPC: 60051     │    │ gRPC: 60050     │ │
│  │ HTTP: 50051     │    │                 │    │                 │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘ │
│           │                       │                       │         │
│           └───────────────────────┼───────────────────────┘         │
│                                   │                                 │
│                    ┌─────────────────┐                             │
│                    │ prover-network  │                             │
│                    │ (Docker Network)│                             │
│                    └─────────────────┘                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```