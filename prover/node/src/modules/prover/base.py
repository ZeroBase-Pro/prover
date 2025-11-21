from abc import ABC

class Prover(ABC):
    def __init__(self, address):
        self.address = address

    async def prove(self, input_data: str, circuit_template_id: str):
        raise NotImplementedError("This prover does not support the prove method")
    
    async def prove_with_witness(self, input_data: str, circuit_template_id: str):
        raise NotImplementedError("This prover does not support the prove_with_witness method")
    
    async def prove_offchain(self, input_data: str, circuit_template_id: str):
        raise NotImplementedError("This prover does not support the prove_offchain method")
    
    async def prove_nosha256(self, input_data: str, circuit_template_id: str, length: int):
        raise NotImplementedError("This prover does not support the prove_nosha256 method")
    
    async def prove_nosha256_with_witness(self, input_data: str, circuit_template_id: str, length: int):
        raise NotImplementedError("This prover does not support the prove_nosha256_with_witness method")
    
    async def prove_nosha256_offchain(self, input_data: str, circuit_template_id: str, length: int):
        raise NotImplementedError("This prover does not support the prove_nosha256_offchain method")

    async def get_running_prove_tasks(self, input_data: str, circuit_template_id: str, length: int):
        raise NotImplementedError("This prover does not support the get_running_prove_tasks method")