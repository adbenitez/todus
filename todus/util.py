import random
import re
import string


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
