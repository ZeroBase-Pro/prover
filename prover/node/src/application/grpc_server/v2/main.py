import grpc

from config import Config

from . import prove_service_v2_pb2
from . import prove_service_v2_pb2_grpc

from modules.prove_service.v2 import ProveServiceV2, ProofResult
from modules.hub import Hub
from modules.proof_manager import ProofManager

from utils.constant import OAUTH_PROVIDER_GOOGLE
from utils.constant import TASK_TYPE_ZKLOGIN

class ProveService(prove_service_v2_pb2_grpc.ProveServiceServicer):

    def __init__(self, prove_service: ProveServiceV2, proof_manager:ProofManager, hub: Hub):
        """
        Initialize GrpcServer with dependency injection.

        Args:
            prove_service (ProveService): An instance of ProveService to handle proof generation logic.
        """
        self.prove_service = prove_service
        self.proof_manager = proof_manager
        self.hub = hub
        self.config = Config()
    
    async def Prove(self, request:prove_service_v2_pb2.GenerateProofRequest, context:grpc.aio.ServicerContext):
        """
        Handle the Prove request to generate proof data.

        Args:
            request (ProveRequest): The request object containing base request info.
            context (grpc.aio.ServicerContext): Context information.

        Returns:
            ProveResponse: The response object containing status and proof data.
        """
        # Extract base request parameters
        prover = request.prover                   # Identifier for the prover
        circuit_template_id = request.circuit_template_id  # Circuit template identifier
        payload = request.payload
        is_encrypted = request.is_encrypted             # Indicates if input data is encrypted
        auth_token = request.auth_token                 # Authentication token
        task_type = request.task_type or TASK_TYPE_ZKLOGIN
        length = request.length
        oauth_provider = request.oauth_provider or OAUTH_PROVIDER_GOOGLE

        proof_hash = request.proof_hash

        ok, msg = self.proof_manager.claim_task(proof_hash)
        if ok != True:
            return prove_service_v2_pb2.GenerateProofResponse(
                code=ok,
                msg=msg
            )
                
        proof_result: ProofResult = await self.prove_service.prove(task_type, prover, circuit_template_id, payload, is_encrypted, auth_token, length, oauth_provider)
        
        if proof_result.project_name:
            await self.hub.send_result(proof_result.project_name, proof_hash, proof_result.duration, proof_result.verifiers)

        return prove_service_v2_pb2.GenerateProofResponse(
            code=proof_result.code,
            msg=proof_result.msg,
            proof=proof_result.proof,
            proof_solidity=proof_result.proof_solidity,
            proof_bytes=proof_result.proof_bytes,
            public_witness=proof_result.public_witness,
            public_witness_bytes=proof_result.public_witness_bytes
        )

def create_grpc_prover_service(grpc_server:grpc.Server, prove_service: ProveService, proof_manager:ProofManager, hub: Hub):
    """
    Start the gRPC server and listen on the specified host and port.

    Args:
        host (str): Host to bind the gRPC server to.
        port (int): Port to bind the gRPC server to.
        prove_service (ProveService): The ProveService instance to inject into the GrpcServer.

    Returns:
        grpc.aio.Server: The configured gRPC server.
    """
    # Add the ProveService to the server with dependency injection
    service = ProveService(prove_service, proof_manager, hub)
    prove_service_v2_pb2_grpc.add_ProveServiceServicer_to_server(service, grpc_server)
    # Bind the server to the specified address and port

    return grpc_server