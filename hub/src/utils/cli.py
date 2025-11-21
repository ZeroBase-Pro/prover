import argparse
import os
import logging

from modules.encryptor import RSAEncryption
from utils.logger import setup_logger
from utils.constant import CLI_LOGGER, PUBLIC_KEY, PRIVATE_KEY


def init_key(key_size, path, logger):
    """Generate RSA keys and write them to path.

    logger: a logging.Logger instance used for messages.
    """
    if key_size < 1024 or key_size > 8096:
        logger.error("The range is [1024~8096]")
        return

    encryptor = RSAEncryption()
    public_key_path = os.path.join(path, PUBLIC_KEY)
    private_key_path = os.path.join(path, PRIVATE_KEY)

    encryptor.generate_keys(key_size)
    encryptor.serialize_keys()

    with open(public_key_path, mode='w') as f:
        f.write(encryptor.public_key)
        logger.info(f"Public key is created in [{public_key_path}]")

    with open(private_key_path, mode='w') as f:
        f.write(encryptor.private_key)
        logger.info(f"Private key is created in [{private_key_path}]")

def main():
    # Delay creating Config and logger to avoid side-effects at import time
    from config import Config
    config = Config()
    setup_logger(CLI_LOGGER, config.Env.logs_path, "M", logging.DEBUG)
    logger = logging.getLogger(CLI_LOGGER)

    parser = argparse.ArgumentParser(description="RSA Key Generator CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # `init_keys` command
    parser_init_keys = subparsers.add_parser("init_keys", help="Initialize RSA keys")
    parser_init_keys.add_argument(
        "--key_size",
        type=int,
        default=4096,
        help="Key size for RSA encryption (range: 4096~8096)",
    )
    parser_init_keys.add_argument(
        "--path",
        type=str,
        default=".",
        help="Path to save the generated keys",
    )

    args = parser.parse_args()

    if args.command == "init_keys":
        init_key(args.key_size, args.path, logger)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()