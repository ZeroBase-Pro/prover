# Prover

This directory contains:

- `node/`: gateway service
- `circom-prover/`: Circom prover runtime
- `gnark-prover/`: Gnark prover runtime
- `run.sh`: helper to start all three services

The node, circom prover, and gnark prover are started from published Docker Hub images.

## Required files

### Node

- `node/src/config/node.py`
- `node/src/session_keys/public_key`
- `node/certs/tls.crt`
- `node/certs/tls.key`

### Circom prover

- `circom-prover/certs/tls.crt`
- `circom-prover/certs/tls.key`

### Gnark prover

- `gnark-prover/certs/tls.crt`
- `gnark-prover/certs/tls.key`

## Node configuration

Update `node/src/config/node.py`:

- `Hub.API.url`
- `Hub.Info.grpc`
- `Hub.Info.http`
- `Env.node_register_token`
- `Env.verify_hub_tls`
- `Env.verify_prover_tls`

The node now uses `node.py` as the active default config and `MODE=NODE`.

## Permissions

```bash
chmod +x run.sh
chmod +x node/pull.sh
chmod +x circom-prover/pull.sh
chmod +x gnark-prover/pull.sh
chmod 644 node/src/session_keys/public_key
chmod 644 node/certs/tls.crt
chmod 644 node/certs/tls.key
chmod 644 circom-prover/certs/tls.crt
chmod 644 circom-prover/certs/tls.key
chmod 644 gnark-prover/certs/tls.crt
chmod 644 gnark-prover/certs/tls.key
```

## Start all services

```bash
./run.sh --mode gpu --node-grpc 50050 --node-http 50051 --circom-port 60051 --gnark-port 60050 --hub https://your-hub-host:9000
```

CPU mode:

```bash
./run.sh --mode cpu --node-grpc 50050 --node-http 50051 --circom-port 60051 --gnark-port 60050 --hub https://your-hub-host:9000
```

## Start services individually

Node:

```bash
cd node
./pull.sh 50050 50051 https://your-hub-host:9000
```

Circom prover:

```bash
cd circom-prover
./pull.sh gpu 60051
```

Gnark prover:

```bash
cd gnark-prover
./pull.sh gpu 60050
```

## Verify

```bash
docker ps
docker logs -f node-container
docker logs -f circom-prover
docker logs -f gnark-prover
curl -k https://127.0.0.1:50051/ping
openssl s_client -connect 127.0.0.1:50050 -servername zerobase-self-signed </dev/null
```
