import datetime
import logging
import random
import hashlib
import json

class NodeList:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        self.nodes = {}
        self.last_poh_index = None
        self.timeout = 30
    
    def _generate_poh(self, grpc_info, http_info, timestamp):
        data = {
            "grpc_info": grpc_info,
            "http_info": http_info,
            "timestamp": timestamp,
            "last_poh_index": self.last_poh_index
        }
        hash_input = json.dumps(data, sort_keys=True).encode()
        hash_output = hashlib.sha256(hash_input).hexdigest()
        return hash_output
    
    def _generate_unique(self, grpc_info, http_info):
        data = {
            "grpc_info": grpc_info,
            "http_info": http_info,
        }
        hash_input = json.dumps(data, sort_keys=True).encode()
        hash_output = hashlib.sha256(hash_input).hexdigest()
        return hash_output
    
    def add(self, grpc_info, http_info):
        timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        
        index = self._generate_unique(grpc_info, http_info)
        poh_index = self._generate_poh(grpc_info, http_info, timestamp)
        
        if self.last_poh_index is None:
            self.last_poh_index = poh_index
        
        self.nodes[index] = {
            "grpc_info": grpc_info,
            "http_info": http_info,
            "timestamp": timestamp,
            "poh": poh_index
        }
        
        self.last_poh_index = poh_index
    
    def remove(self, index):
        if index in self.nodes:
            del self.nodes[index]
    
    def get_node(self, size=4):
        if size > len(self.nodes):
            return [(self.nodes[index]["grpc_info"], self.nodes[index]["http_info"], self.nodes[index]["timestamp"], self.nodes[index]["poh"]) for index in self.nodes.keys()]
        
        index_list = random.sample(list(self.nodes.keys()), size)
        return [(self.nodes[index]["grpc_info"], self.nodes[index]["http_info"], self.nodes[index]["timestamp"], self.nodes[index]["poh"]) for index in index_list]

    def remove_inactive_nodes(self):
        current_time = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        self.nodes = {index: node for index, node in self.nodes.items() if (current_time - node["timestamp"]) <= self.timeout}

    def set_timeout(self, timeout):
        self.timeout = timeout
