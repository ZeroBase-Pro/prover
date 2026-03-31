from pathlib import Path


def _default_tls_path(filename: str) -> str:
    candidates = [
        Path("/app/certs") / filename,
        Path(__file__).resolve().parents[2] / "certs" / filename,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


class Config:
    class Env:
        app = "zerobase-hub"
        debug = False
        logs_path = "src/logs"
        crypto_keys_path = "src/crypto_keys"
        session_keys_path = "src/session_keys"
        require_tls = True
        tls_certfile = _default_tls_path("tls.crt")
        tls_keyfile = _default_tls_path("tls.key")

    class Server:
        class Sanic:
            host = "0.0.0.0"
            port = 9000
            forwarded_secret = "ABCDEFG"
            real_ip_header = "cf-connecting-ip"
            proxies_count = 2
            cors_domains = ["*"]

    class Explorer:
        api = "https://scan.zerobase.pro"
        key_path = "src/explorer_public_key"

    class Security:
        node_register_token = ""
        allowed_node_hosts = []
        allowed_node_cidrs = []
        verify_node_tls = False
        tls_certfile = _default_tls_path("tls.crt")
