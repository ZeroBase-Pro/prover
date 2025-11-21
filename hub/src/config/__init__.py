import os
import logging
import importlib
from dotenv import load_dotenv
import threading
from .hub import Config as HubConfig

load_dotenv()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(process)d] [%(levelname)s] - %(name)s "
                                               "(%(filename)s:%(lineno)d) - %(message)s")

class Config:
    _instance = None
    _locker = threading.Lock()

    def __new__(cls) -> HubConfig:
        with cls._locker:
            if cls._instance is None:
                cls._instance = super(Config, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> HubConfig:
        if self._initialized:  # Prevent double initialization
            return

        self._load_config()
        self._initialized = True

    def _load_config(self):
        """
        Dynamically load configuration based on MODE environment variable.
        """
        mode = os.environ.get('MODE', 'HUB').lower()
        try:
            custom_config_module = importlib.import_module(f'.{mode}', package=__package__)
            self._config: HubConfig = custom_config_module.Config  # instantiate the concrete config class
            logging.info(f"[Config] - [{mode}] is loaded")
        except ImportError:
            logging.error(f"[Config] - [{mode}] cannot be imported, falling back to [SAMPLE]")
            self._config = HubConfig()  # use default configuration
        finally:
            os.environ.setdefault('LOG_PATH', self._config.Env.logs_path or "logs")

    def __getattr__(self, name):
        """
        Dynamically proxy configuration attributes to the loaded config instance.
        """
        if hasattr(self._config, name):
            return getattr(self._config, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")