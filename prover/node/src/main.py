import argparse
import logging
import asyncio

from config import Config
from utils.logger_util import setup_logger, patch_framework_loggers
from utils.constant import CLI_LOGGER, PROVE_SERVICE_LOGGER
from utils.crypto_key_util import CryptoKey
from utils.server_util import ServerBuilder

# Initialize configuration
config = Config()

setup_logger(config.Env.app, config.Env.logs_path, "MIDNIGHT", logging.INFO, True)
patch_framework_loggers()

logger = logging.getLogger(CLI_LOGGER)

async def server(grpc_host: str, grpc_port: str, fastapi_host: str, fastapi_port: str, session_key_path: str, hub_api: str):
    """
    Start the server, including gRPC and FastAPI.
    """
    builder = ServerBuilder(config)  # Use global configuration
    server = await builder.build(
        hub_api=hub_api,
        grpc_host=grpc_host,
        grpc_port=int(grpc_port),  # grpc_port is str, need to convert to int
        fastapi_host=fastapi_host,
        fastapi_port=int(fastapi_port)
    )
    logger.info("Server initialized, running now...")
    await server.run()

def crypto_keys(path: str, size: int):
    """
    Generate encryption keys.

    Args:
        path (str): Path to save the keys.
        size (int): Key size in bits.
    """
    if size < 2048 or size > 8096:
        logger.error("The key size range is [2048~8096].")
        return
    crypto_key = CryptoKey(path)
    crypto_key.generate_keys(size)
    logger.info(f"Crypto keys generated at {path} with size {size} bits.")

def main():
    # Create argument parser
    parser = argparse.ArgumentParser(description="Command-line tool for server and crypto key management.")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # server subcommand
    server_parser = subparsers.add_parser('server', help='Start the server.')
    server_parser.add_argument('-grpc_host', type=str, default=config.Server.Grpc.host, help='gRPC host')
    server_parser.add_argument('-grpc_port', type=str, default=config.Server.Grpc.port, help='gRPC port')
    server_parser.add_argument('-fastapi_host', type=str, default=config.Server.FastAPI.host, help='FastAPI host')
    server_parser.add_argument('-fastapi_port', type=int, default=config.Server.FastAPI.port, help='FastAPI port')
    server_parser.add_argument('-hub_api', type=str, default=config.Hub.API.url, help='Hub API URL')
    server_parser.add_argument('-session_key', type=str, default=config.Env.session_keys_path, help='Session key path')
    server_parser.set_defaults(func=server)

    # crypto_keys subcommand
    crypto_keys_parser = subparsers.add_parser('crypto_keys', help='Generate cryptographic keys.')
    crypto_keys_parser.add_argument('-p', '--path', type=str, default=config.Env.crypto_keys_path, help='Path to save keys')
    crypto_keys_parser.add_argument('-s', '--size', type=int, required=True, help='Key size in bits (required)')
    crypto_keys_parser.set_defaults(func=crypto_keys)

    args = parser.parse_args()

    # Call corresponding function based on subcommand
    if hasattr(args, 'func'):
        if args.command == 'server':
            asyncio.run(
                args.func(
                    grpc_host=args.grpc_host,
                    grpc_port=args.grpc_port,
                    fastapi_host=args.fastapi_host,
                    fastapi_port=args.fastapi_port,
                    session_key_path=args.session_key,
                    hub_api=args.hub_api
                )
            )
        elif args.command == 'crypto_keys':
            args.func(path=args.path, size=args.size)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
