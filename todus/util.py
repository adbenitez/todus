import json
import logging.handlers
import os
import random
import re
import string


def get_config() -> dict:
    """Get CLI program's configuration."""
    with open(CONFIG_PATH, encoding="utf-8") as file:
        return json.load(file)


def save_config(config: dict) -> None:
    """Save CLI program's configuration."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        return json.dump(config, file)


def get_logger() -> logging.Logger:
    """Create file logger."""
    logger = logging.Logger(__name__.split(".", maxsplit=1)[0])
    logger.parent = None
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    log_path = os.path.join(PROGRAM_FOLDER, "log.txt")
    fhandler = logging.handlers.RotatingFileHandler(
        log_path, backupCount=3, maxBytes=1024 ** 2
    )
    fhandler.setLevel(logging.DEBUG)
    fhandler.setFormatter(formatter)
    logger.addHandler(fhandler)

    return logger


def generate_token(length: int) -> str:
    """Generate random alphanumeric string of the requested length."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def normalize_phone_number(phone_number: str) -> str:
    """Convert the given phone number string to the format expected by the s3 server."""
    phone_number = "".join(phone_number.lstrip("+").split())
    match = re.match(r"(53)?(\d{8})", phone_number)
    assert match, "Invalid phone number"
    return "53" + match.group(2)


PROGRAM_FOLDER = os.path.expanduser("~/.todus")
CONFIG_PATH = os.path.join(PROGRAM_FOLDER, "config.json")
if not os.path.exists(PROGRAM_FOLDER):
    os.makedirs(PROGRAM_FOLDER)
if not os.path.exists(CONFIG_PATH):
    save_config(
        {
            "accounts": [],
        }
    )
