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

    class Server:
        class Grpc:
            host = "[::]"
            port = 50050

        class FastAPI:
            host = "127.0.0.1"
            port = 50051

    class Hub:
        class API:
            url = "http://host.docker.internal:9000"

        class Info:
            grpc = "127.0.0.1:50050"
            http = "http://127.0.0.1:50051"

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