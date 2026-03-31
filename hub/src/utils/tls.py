import os
import ssl
from functools import lru_cache
from typing import Optional

import grpc
from cryptography import x509
from cryptography.x509.oid import NameOID


def normalize_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    value = path.strip()
    if not value:
        return None
    return os.path.abspath(value)


@lru_cache(maxsize=None)
def load_pem_bytes(path: Optional[str]) -> Optional[bytes]:
    normalized = normalize_path(path)
    if not normalized:
        return None
    with open(normalized, "rb") as file:
        return file.read()


@lru_cache(maxsize=None)
def client_ssl_context(path: Optional[str]) -> ssl.SSLContext:
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    normalized = normalize_path(path)
    if normalized:
        context.load_verify_locations(cafile=normalized)
    return context


def aiohttp_ssl_param(verify_tls: bool, tls_certfile: Optional[str]):
    if not verify_tls:
        return False
    normalized = normalize_path(tls_certfile)
    if not normalized:
        return None
    return client_ssl_context(normalized)


@lru_cache(maxsize=None)
def grpc_target_name_override(path: Optional[str]) -> Optional[str]:
    cert_bytes = load_pem_bytes(path)
    if not cert_bytes:
        return None

    certificate = x509.load_pem_x509_certificate(cert_bytes)
    try:
        subject_alt_name = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        dns_names = subject_alt_name.get_values_for_type(x509.DNSName)
        if dns_names:
            return dns_names[0]
        ip_addresses = subject_alt_name.get_values_for_type(x509.IPAddress)
        if ip_addresses:
            return str(ip_addresses[0])
    except x509.ExtensionNotFound:
        pass

    common_names = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if common_names:
        return common_names[0].value
    return None


def grpc_channel_credentials(path: Optional[str]) -> grpc.ChannelCredentials:
    return grpc.ssl_channel_credentials(root_certificates=load_pem_bytes(path))


def grpc_channel_options(verify_tls: bool, tls_certfile: Optional[str]) -> list[tuple[str, str]]:
    if verify_tls:
        return []

    override = grpc_target_name_override(tls_certfile)
    if not override:
        return []

    return [
        ("grpc.ssl_target_name_override", override),
        ("grpc.default_authority", override),
    ]
