# Prover Network

Open-source bundle for Zerobase proving infrastructure. The codebase is split so you can deploy only what you need:

- `hub/` — coordination service that tracks available prover nodes, dispatches work, and routes results.
- `prover/` — prover runtime that packages the Node gateway plus Circom and Gnark proving services (CPU/GPU).

Use this README to choose where to go; each subfolder has its own detailed guide.

## Repository Layout

```
zerobase-prover/
├─ hub/             # Hub service (HTTP/Sanic + gRPC helpers)
│  └─ README.md     # Configure keys, set ports, and start the hub container
├─ prover/          # Prover stack (Node gateway + Circom Prover + Gnark Prover)
│  └─ README.md     # Configure node/circom/gnark and run all services
└─ README.md        # You are here (top-level overview)
```

## Where to Start

- **Run the hub** if you operate a registry/dispatcher that nodes report to and clients query for available proving endpoints. See `hub/README.md` for configuration and `run.sh start` usage.
- **Run the prover stack** if you need the proving services on a machine. See `prover/README.md` for config, CPU/GPU modes, and `run.sh` commands.

## Before you begin

This repository is intended to run on a server-grade machine with a Trusted Execution Environment (TEE) and a public IP (or properly configured NAT/port forwarding). Running the services on consumer/home devices or laptops is not recommended.

- **Why:** The proving services expect external connectivity and may require public IP mapping for gRPC/HTTP endpoints and inter-service communication.
- **What to use:** A TEE-capable server or cloud instance with TEE support and a static/public IP address.

## Common Prerequisites

- Docker and Docker Compose installed; ability to run `sudo docker ...`.
- For GPU proving, an NVIDIA driver compatible with CUDA 12.x and the NVIDIA Container Toolkit.
- Public/static IP or correct port forwarding if exposing services externally.

## Contributing

Issues and PRs are welcome. If you change container interfaces or config shapes, update the corresponding `hub/README.md` or `prover/README.md` so users know how to run the new version.