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
            port = 9000
            forwarded_secret = "ABCDEFG"
            real_ip_header = "cf-connecting-ip"
            proxies_count = 2
            cors_domains = ['*']

    class Explorer:
        api = ""
        key_path = ""