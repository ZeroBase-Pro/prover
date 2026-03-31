# Prover Network

This repository is split into two deployable parts:

- `hub/`: hub service for node registration, node discovery, task dispatch, and result routing.
- `prover/`: node gateway plus Circom and Gnark prover services.

The hub is built locally. The prover stack runs from published Docker Hub images.

## Requirements

- Linux server or TEE machine
- Docker and Docker Compose
- Public IP or valid port forwarding
- NVIDIA driver and NVIDIA Container Toolkit for GPU mode

## TLS

The current release uses self-signed certificates.

- HTTP uses HTTPS.
- gRPC uses TLS.
- Default behavior is encrypted transport with relaxed certificate verification.

Create one certificate pair and place it under each runtime directory as `certs/tls.crt` and `certs/tls.key`.

## Start

- For the hub, see `hub/README.md`.
- For the prover stack, see `prover/README.md`.

## Notes

- Do not commit real session keys or certificates.
- `prover/` does not build prover images locally. It pulls published images from Docker Hub.
