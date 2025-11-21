from abc import ABC, abstractmethod
import ujson
import os
import logging
import threading


class OAuthProvider(ABC):
    
    @abstractmethod
    def verify(self, input_data: str):
        pass
    
    @abstractmethod
    def update_jwks(self):
        pass


class OAuthProviderResolver:
    """
    Used to determine if a template_id is bound to an OAuthProvider,
    and return the bound provider name (if exists).
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(OAuthProviderResolver, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_file_path: str):
        if self._initialized:
            return

        self.config_file_path = config_file_path
        self.template_provider_map = {}
        self._load_config()
        self._initialized = True

    def _load_config(self):
        """Load template_id to provider mapping configuration"""
        try:
            with open(self.config_file_path, 'r') as f:
                self.template_provider_map = ujson.load(f)
            logging.info("OAuth provider mappings loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load OAuth provider mappings: {e}")
            self.template_provider_map = {}

    def resolve_provider(self, template_id: str) -> str | None:
        """
        Return the bound OAuthProvider name based on template_id.
        Return None if not found.
        """
        provider_info = self.template_provider_map.get(template_id)
        if provider_info and isinstance(provider_info, dict):
            return provider_info.get("provider")
        return None