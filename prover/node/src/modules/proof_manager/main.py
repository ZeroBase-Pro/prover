import pickle
import os
import time
import logging
import threading
from utils.constant import STATUS_CODE_TASK_INVALID, STATUS_CODE_TASK_NOT_FOUND, TASK_STATUS_PENGDING, TASK_STATUS_RUNNING

class ProofManager:
    _instance = None
    _locker = threading.Lock()
    _SAVE_INTERVAL = 5  

    def __new__(cls, *args, **kwargs):
        with cls._locker:
            if cls._instance is None:
                cls._instance = super(ProofManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, cache_path):
        if self._initialized == True:
            return

        self.cache_path = cache_path
        self.cache = {}
        self._load_cache()
        self._dirty = False  
        self._stop_event = threading.Event()  
        self._write_lock = threading.Lock()  
        self._start_background_flush()  
        self._initialized = True

    def _drop_expired(self):  
        current_time = time.time()  
        logging.info("Cache loaded. Size BEFORE drop_expired: %d %d", len(self.cache), current_time)
        keys_to_delete = [key for key, (_, expiry) in self.cache.items()
                          if expiry is not None and expiry <= current_time]  
        all_keys = [(key, expiry) for key, (_, expiry) in self.cache.items()]

        logging.info("All keys in cache: %s", all_keys)

        for key in keys_to_delete:  
            del self.cache[key]  
        if keys_to_delete:  
            logging.info("Expired keys removed during load/save: %s", keys_to_delete)  
        logging.info("Cache size AFTER drop_expired: %d", len(self.cache))

    def _load_cache(self):
        """Load cache from file"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'rb') as f:
                    logging.info("Cache loaded successfully from %s", self.cache_path)
                    self.cache = pickle.load(f)
                    self._drop_expired()
            except (IOError, pickle.PickleError) as e:
                logging.error("Failed to load cache: %s", e)
        logging.warning("Cache file not found, starting with an empty cache.")
        return {}

    def get(self, key):
        """Get value from cache with automatic expiry handling"""
        if key in self.cache:
            value, expiry = self.cache[key]
            if expiry is None or expiry > time.time():
                logging.info("Cache hit for key: %s", key)
                return value
            else:
                # If key is expired, delete it
                logging.info("Cache expired for key: %s", key)
                del self.cache[key]
                self._dirty = True  
        else:
            logging.info("Cache miss for key: %s", key)
        return None

    def set(self, key, value, ttl=60):
        """
        Update cache and persist to file 
        :param key: Cache key
        :param value: Cache value
        :param ttl: Time to live in seconds, None means no expiration
        """
        expiry = time.time() + ttl if ttl is not None else None
        self.cache[key] = (value, expiry)
        logging.info("Cache updated for key: self.cache:%s", self.cache[key])
        logging.info("Cache updated for key: %s %d %d", key, value, expiry)
        self._dirty = True  

    def _save_cache(self):  

        logging.info("_save_cache start %s , %d", self.cache_path, len(self.cache))  
        try:
            if not self._dirty:
                return  
            with self._write_lock:  
                self._drop_expired()
                with open(self.cache_path, 'wb') as f:
                    logging.info("Saving cache to %s", self.cache)  
                    pickle.dump(self.cache, f)
            logging.info("Cache appended successfully to %s %d", self.cache_path, len(self.cache))  
            self._dirty = False  
        except IOError as e:
            logging.error("Failed to save cache: %s %d", e, len(self.cache))  

    def _start_background_flush(self):  
        def _flush_loop():  
            while not self._stop_event.is_set():  
                time.sleep(self._SAVE_INTERVAL)  
                try:  
                    self._save_cache()  
                except Exception as e:  
                    logging.error("Background flush failed: %s", e)  
        t = threading.Thread(target=_flush_loop, daemon=True)  
        t.start()  
    def clean_expired(self):
        """Clean expired keys"""
        current_time = time.time()
        keys_to_delete = [key for key, (_, expiry) in self.cache.items()
                          if expiry is not None and expiry <= current_time]
        for key in keys_to_delete:
            del self.cache[key]
        if keys_to_delete:
            logging.info("Expired keys cleaned: %s", keys_to_delete)
            self._dirty = True  
            self._save_cache()  

    def claim_task(self, proof_hash: str) -> bool:
        status = self.get(proof_hash)
        if status is None:
            return STATUS_CODE_TASK_NOT_FOUND, "Proof hash does not exist"
        if status != TASK_STATUS_PENGDING:
            return STATUS_CODE_TASK_INVALID, "Proof hash is invalid"
        self.set(proof_hash, TASK_STATUS_RUNNING)
        return True, "Successfully"

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    cache_path = "proof_cache.pkl"
    manager = ProofManager(cache_path)
    start = time.perf_counter()
    print (start)
    key = 1
    manager.set(key, 1, ttl=5)

    print("Cached value:", manager.get(key))
    test = manager.get(key)
    print (test == 2)
    

    time.sleep(6)
    end = time.perf_counter()
    print (end)

    print (end-start)
    print("Cached value after expiry:", manager.get(key))

    manager.clean_expired()