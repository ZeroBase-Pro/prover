# Hub

## Files

- `run.sh`: local build and container lifecycle helper
- `docker-compose.yml`: runtime definition
- `src/config/hub.py`: default configuration
- `src/session_keys/`: required hub key pair
- `certs/`: TLS certificate pair

## Required files

Place these files before start:

- `src/session_keys/private_key`
- `src/session_keys/public_key`
- `src/explorer_public_key`
- `certs/tls.crt`
- `certs/tls.key`

Generate session keys with:

```bash
python -m src.utils.cli init_keys --path src/session_keys
```

## Configuration

Update `src/config/hub.py`:

- `Server.Sanic.port`
- `Security.node_register_token`
- `Security.verify_node_tls`
- `Env.require_tls`
- `Explorer.key_path` if you store the explorer public key somewhere else

Default runtime expects TLS to stay enabled.

## Permissions

```bash
chmod +x run.sh
chmod 600 src/session_keys/private_key
chmod 644 src/session_keys/public_key
chmod 644 certs/tls.crt
chmod 644 certs/tls.key
```

## Build and start

```bash
docker compose build --no-cache
./run.sh start
```

Use a custom config file if needed:

```bash
./run.sh start ./configs/local_hub.py
```

## Verify

```bash
docker compose ps
docker compose logs -f
curl -k https://127.0.0.1:9000/api/v1/hub/node/status
```
