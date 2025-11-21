import datetime
import logging
import random
import hashlib
import json
import time

class NodeList:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance
    
    def _init(self):
        """Initialize the node list and other necessary state variables."""
        self.nodes = {}  # Dictionary storing node info; key is a PoH-based unique index
        self.last_poh_index = None  # Track the last node's PoH index
        self.timeout = 30  # Default timeout in seconds
    
    def _generate_poh(self, grpc_info, http_info, timestamp):
        """Generate a PoH (proof-of-history) index by hashing grpc/http info, timestamp and last PoH."""
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
        """Generate a stable unique id for a node based on grpc and http info."""
        data = {
            "grpc_info": grpc_info,
            "http_info": http_info,
        }
        hash_input = json.dumps(data, sort_keys=True).encode()
        hash_output = hashlib.sha256(hash_input).hexdigest()
        return hash_output
    
    def add(self, grpc_info, http_info):
        """Add a node using grpc and http info. Uses PoH index as the node's unique identifier."""
        timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        
        index = self._generate_unique(grpc_info, http_info)
    # Generate PoH index
        poh_index = self._generate_poh(grpc_info, http_info, timestamp)
        
        # If this is the first node, initialize last_poh_index
        if self.last_poh_index is None:
            self.last_poh_index = poh_index

        # Store node data
        self.nodes[index] = {
            "grpc_info": grpc_info,
            "http_info": http_info,
            "timestamp": timestamp,
            "poh": poh_index
        }
        
    # Update last_poh_index to the current node's PoH index
        self.last_poh_index = poh_index
    
    def remove(self, index):
        """Remove a node by its index (the unique id)."""
        if index in self.nodes:
            del self.nodes[index]
    
    def get_node(self, size=4):
        """Return a list of random nodes (or all nodes if size > node count)."""
        if size > len(self.nodes):
            return [(self.nodes[index]["grpc_info"], self.nodes[index]["http_info"], self.nodes[index]["timestamp"], self.nodes[index]["poh"]) for index in self.nodes.keys()]
        
        index_list = random.sample(list(self.nodes.keys()), size)
        return [(self.nodes[index]["grpc_info"], self.nodes[index]["http_info"], self.nodes[index]["timestamp"], self.nodes[index]["poh"]) for index in index_list]

    def remove_inactive_nodes(self):
        """Remove nodes that have been inactive longer than the configured timeout."""
        current_time = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        
    # Filter out nodes that have timed out
        self.nodes = {index: node for index, node in self.nodes.items() if (current_time - node["timestamp"]) <= self.timeout}

    def set_timeout(self, timeout):
        """Set node inactivity timeout in seconds."""
        self.timeout = timeout

# Example usage
if __name__ == "__main__":
    test = NodeList()
    test.set_timeout(3)
    test.add("grpc_address_1", "http_address_1")  # new node
    test.add("grpc_address_1", "http_address_1")  # duplicate node (same id)
    test.add("grpc_address_2", "http_address_2")  # new node
    test.add("grpc_address_3", "http_address_3")  # new node
    print("Node info:", test.nodes)
    time.sleep(4)

    # Remove inactive nodes
    test.remove_inactive_nodes()
    print("Node info:", test.nodes)

    test.add("grpc_address_3", "http_address_3")  # re-add node
    print("Node info:", test.nodes)

