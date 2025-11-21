import sanic
from typing import Iterable, Optional


def create_app(
    app: str,
    host: str,
    port: int,
    forwarded_secret: str = "",
    real_ip_header: str = "",
    proxies_count: int = 0,
    cors_domains: Optional[Iterable[str]] = None,
):
    """Create and configure a Sanic app safely.

    cors_domains can be None or an iterable of origins. Internally we store
    as a semicolon-separated string for current codebase compatibility.
    """
    server = sanic.Sanic(app)

    server.config.SERVER_NAME = f"{host}:{port}"
    server.config.FORWARDED_SECRET = forwarded_secret
    server.config.REAL_IP_HEADER = real_ip_header
    server.config.PROXIES_COUNT = proxies_count
    if isinstance(cors_domains, str):
        cors_list = [cors_domains]
    elif cors_domains is None:
        cors_list = []
    else:
        cors_list = list(cors_domains)

    server.config.CORS_ORIGINS = ";".join(cors_list)

    return server