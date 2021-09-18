import functools
import logging
import os
import string
import time
from http.client import IncompleteRead
from typing import Callable

import requests.exceptions

from .s3 import get_real_url, reserve_url
from .util import generate_token


class ToDusClient:
    """Class to interact with the ToDus API."""

    def __init__(
        self,
        version_name: str = "0.38.34",
        version_code: str = "21805",
        logger: logging.Logger = logging,  # type: ignore
    ) -> None:
        self.version_name = version_name
        self.version_code = version_code
        self.logger = logger

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept-Encoding": "gzip",
            }
        )
        self.session.request = functools.partial(_request, self.session.request)  # type: ignore

    @property
    def auth_ua(self) -> str:
        """User Agent used for authentication."""
        return f"ToDus {self.version_name} Auth"

    @property
    def upload_ua(self) -> str:
        """User Agent used for uploads."""
        return f"ToDus {self.version_name} HTTP-Upload"

    @property
    def download_ua(self) -> str:
        """User Agent used for downloads."""
        return f"ToDus {self.version_name} HTTP-Download"

    def request_code(self, phone_number: str) -> None:
        """Request server to send verification SMS code."""
        headers = {
            "Host": "auth.todus.cu",
            "User-Agent": self.auth_ua,
            "Content-Type": "application/x-protobuf",
        }
        data = (
            b"\n\n"
            + phone_number.encode()
            + b"\x12\x96\x01"
            + generate_token(150).encode()
        )
        url = "https://auth.todus.cu/v2/auth/users.reserve"
        with self.session.post(url, data=data, headers=headers) as resp:
            resp.raise_for_status()

    def validate_code(self, phone_number: str, code: str) -> str:
        """Validate phone number with received SMS code.

        Returns the account password.
        """
        headers = {
            "Host": "auth.todus.cu",
            "User-Agent": self.auth_ua,
            "Content-Type": "application/x-protobuf",
        }
        data = (
            b"\n\n"
            + phone_number.encode()
            + b"\x12\x96\x01"
            + generate_token(150).encode()
            + b"\x1a\x06"
            + code.encode()
        )
        url = "https://auth.todus.cu/v2/auth/users.register"
        with self.session.post(url, data=data, headers=headers) as resp:
            resp.raise_for_status()
            if b"`" in resp.content:
                index = resp.content.index(b"`") + 1
                return resp.content[index : index + 96].decode()
            return resp.content[5:166].decode()

    def login(self, phone_number: str, password: str) -> str:
        """Login with phone number and password to get an access token."""
        headers = {
            "Host": "auth.todus.cu",
            "user-agent": self.auth_ua,
            "content-type": "application/x-protobuf",
        }
        data = (
            b"\n\n"
            + phone_number.encode()
            + b"\x12\x96\x01"
            + generate_token(150).encode()
            + b"\x12\x60"
            + password.encode()
            + b"\x1a\x05"
            + self.version_code.encode()
        )
        url = "https://auth.todus.cu/v2/auth/token"
        with self.session.post(url, data=data, headers=headers) as resp:
            resp.raise_for_status()
            token = "".join([c for c in resp.text if c in string.printable])
            return token

    def upload_file(self, token: str, data: bytes, size: int = None) -> str:
        """Upload data and return the download URL."""
        up_url, down_url = reserve_url(token, size or len(data))
        headers = {
            "User-Agent": self.upload_ua,
            "Authorization": f"Bearer {token}",
        }
        with self.session.put(
            url=up_url,
            data=data,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
        return down_url

    def download_file(self, token: str, url: str, path: str) -> int:
        """Download file URL.

        Returns the file size.
        """
        temp_path = f"{path}.part"
        url = get_real_url(token, url)
        headers = {
            "User-Agent": self.download_ua,
            "Authorization": f"Bearer {token}",
        }
        size = -1
        with open(temp_path, "ab") as file:
            pos = file.tell()
            while pos < size or size == -1:
                if pos:
                    headers["Range"] = f"bytes={pos}-"
                try:
                    with self.session.get(
                        url=url, headers=headers, stream=True
                    ) as resp:
                        resp.raise_for_status()
                        size = pos + int(resp.headers["Content-Length"])
                        try:
                            for chunk in resp.iter_content(chunk_size=10):
                                file.write(chunk)
                        except requests.exceptions.ConnectionError as err:
                            self.logger.exception(err)
                            time.sleep(5)
                except IncompleteRead as err:
                    self.logger.exception(err)
                    time.sleep(5)
                except requests.exceptions.ReadTimeout as err:
                    self.logger.exception(err)
                    time.sleep(5)
                pos = file.tell()
        os.rename(temp_path, path)
        return size


class ToDusClient2(ToDusClient):
    """Class to interact with the ToDus API."""

    def __init__(self, phone_number: str, password: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.phone_number = phone_number
        self.password = password
        self.token = ""

    @property
    def registered(self) -> bool:
        """True if this client has a phone_number and password set."""
        return bool(self.phone_number and self.password)

    @property
    def logged(self) -> bool:
        """True if client is logged in."""
        return bool(self.token)

    def request_code(self) -> None:  # noqa
        """Request server to send verification SMS code."""
        super().request_code(self.phone_number)

    def validate_code(self, code: str) -> None:  # noqa
        """Validate phone number with received SMS code.

        Returns the account password.
        """
        self.password = super().validate_code(self.phone_number, code)

    def login(self) -> None:  # noqa
        """Login with phone number and password to get an access token."""
        assert self.password, "Can't login without password"
        self.token = super().login(self.phone_number, self.password)

    def upload_file(self, data: bytes, size: int = None) -> str:  # noqa
        """Upload data and return the download URL."""
        assert self.token, "Token needed"
        return super().upload_file(self.token, data, size)

    def download_file(self, url: str, path: str) -> int:  # noqa
        """Download file URL.

        Returns the file size.
        """
        assert self.token, "Token needed"
        return super().download_file(self.token, url, path)


def _request(real_request: Callable, *args, **kwargs) -> requests.Response:
    kwargs.setdefault("timeout", 30)
    resp = real_request(*args, **kwargs)
    if resp.encoding is None:
        # Default Encoding for HTML4 ISO-8859-1 (Latin-1)
        resp.encoding = "latin-1"
    return resp
