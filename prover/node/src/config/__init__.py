import os
import logging
import importlib
from dotenv import load_dotenv
import threading
from .sample import Config as SampleConfig

load_dotenv()

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(process)d] [%(levelname)s] - %(name)s "
                                               "(%(filename)s:%(lineno)d) - %(message)s")

class Config:
    _instance = None
    _locker = threading.Lock()

    def __new__(cls) -> SampleConfig:
        with cls._locker:
            if cls._instance is None:
                cls._instance = super(Config, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> SampleConfig:
        if self._initialized:  # Prevent duplicate initialization
            return

        self._load_config()
        self._initialized = True

    def _load_config(self):
        """
        Load configuration dynamically
        """
        mode = os.environ.get('MODE', 'SAMPLE').lower()
        try:
            custom_config_module = importlib.import_module(f'.{mode}', package=__package__)
            self._config: SampleConfig = custom_config_module.Config  # Instantiate specific config class
            logging.info(f"[Config] - [{mode}] is loaded")
        except ImportError:
            logging.error(f"[Config] - [{mode}] cannot be imported, falling back to [SAMPLE]")
            self._config = SampleConfig()  # Use default configuration
        finally:
            os.environ.setdefault('LOG_PATH', self._config.Env.logs_path or "logs")

    def __getattr__(self, name):
        """
        Dynamic proxy for configuration attributes
        """
        if hasattr(self._config, name):
            return getattr(self._config, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")