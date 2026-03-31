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
        app = "Node"
        debug = False
        logs_path = "./logs"
        crypto_keys_path = "./crypto_keys"
        session_keys_path = "./session_keys/public_key"
        cache_path = "./cache.pkl"
        project_path = "./utils/project.json"
        oauth_provider_resolver_path = "./utils/oauth_provider_resolver.json"
        proxy = ""
        node_register_token = ""
        require_tls = True
        verify_hub_tls = False
        verify_prover_tls = False
        tls_certfile = _default_tls_path("tls.crt")
        tls_keyfile = _default_tls_path("tls.key")

    class Server:
        class Grpc:
            host = "[::]"
            port = 50050

        class FastAPI:
            host = "0.0.0.0"
            port = 50051

    class Hub:
        class API:
            url = "https://your-hub-host"

        class Info:
            grpc = "your-node-host:50050"
            http = "https://your-node-host:50051"

    class Prover:
        class Circom:
            address = "circom-prover:60051"

        class Private:
            address = "gnark-prover:60050"

    class OauthProvider:
        class Google:
            api = "https://www.googleapis.com/oauth2/v3/certs"
            circom_bigint_n = 121
            circom_bigint_k = 17

        class Telegram:
            api = "https://api.zerobase.pro/tomo/api/v1/auth/kid"
            circom_bigint_n = 121
            circom_bigint_k = 17

        class X509Google:
            api = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
            circom_bigint_n = 121
            circom_bigint_k = 17
