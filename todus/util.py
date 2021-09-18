import logging.handlers
import os
import random
import re
import string

PROGRAM_FOLDER = os.path.expanduser("~/.todus")
if not os.path.exists(PROGRAM_FOLDER):
    os.makedirs(PROGRAM_FOLDER)


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
    phone_number = phone_number.lstrip("+").replace(" ", "")
    match = re.match(r"(53)?(\d{8})", phone_number)
    assert match, "Invalid phone number"
    return "53" + match.group(2)
