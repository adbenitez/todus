import functools
import json
import logging
import os
import re
import socket
import ssl
import string
import time
from base64 import b64decode, b64encode
from contextlib import contextmanager
from http.client import IncompleteRead
from threading import Lock
from typing import Callable, Generator

import requests.exceptions

from .errors import AuthenticationError, EndOfStreamError, TokenExpiredError
from .util import generate_token

_BUFFERSIZE = 1024 * 1024


class ToDusClient:
    """Class to interact with the ToDus API."""

    def __init__(
        self,
        version_name: str = "0.40.29",
        version_code: str = "21833",
        logger: logging.Logger = logging,  # type: ignore
    ) -> None:
        self.version_name = version_name
        self.version_code = version_code
        self.logger = logger
        self._lock = Lock()

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept-Encoding": "gzip",
            }
        )
        self.session.request = functools.partial(_request, self.session.request)  # type: ignore

    @contextmanager
    def _get_socket(self) -> Generator:
        with self._lock:
            context = ssl.create_default_context()
            context.check_hostname = False
            _socket = context.wrap_socket(socket.socket(socket.AF_INET))
            _socket.settimeout(15)
            _socket.connect(("im.todus.cu", 1756))
            _socket.send(
                b"<stream:stream xmlns='jc' o='im.todus.cu' xmlns:stream='x1' v='1.0'>"
            )
            with _socket:
                yield _socket

    def _reserve_url(self, token: str, filesize: int, t: int) -> tuple:
        phone, authstr = _parse_token(token)
        sid = generate_token(5)

        with self._get_socket() as ssl_socket:
            while True:
                response = ssl_socket.recv(_BUFFERSIZE).decode()
                if _negociate_start(response, ssl_socket, authstr, sid):
                    continue

                if f"t='result' i='{sid}-1'>" in response:
                    ssl_socket.send(b"<en xmlns='x7' u='true' max='300'/>")
                    ssl_socket.send(
                        (
                            "<iq i='"
                            + sid
                            + "-3' t='get'><query xmlns='todus:purl' type='"
                            + str(t)
                            + "' persistent='false' size='"
                            + str(filesize)
                            + "' room=''></query></iq>"
                        ).encode()
                    )
                    continue

                if response.startswith("<ed u='true' max='300'"):
                    ssl_socket.send(("<p i='" + sid + "-4'></p>").encode())
                    continue

                if response.startswith("<iq o='" + phone + "@im.todus.cu"):
                    match = re.match(r".*put='(.*)' get='(.*)' stat.*", response)
                    assert match, f"Unexpected response: {response}"
                    up_url = match.group(1).replace("amp;", "")
                    down_url = match.group(2)
                    return (up_url, down_url)

                if "<not-authorized/>" in response:
                    raise TokenExpiredError()

                if not response:
                    raise EndOfStreamError()

    def _get_real_url(self, token: str, url: str) -> str:
        authstr = _parse_token(token)[1]
        sid = generate_token(5)

        with self._get_socket() as ssl_socket:
            while True:
                response = ssl_socket.recv(_BUFFERSIZE).decode()
                if _negociate_start(response, ssl_socket, authstr, sid):
                    continue

                if f"t='result' i='{sid}-1'>" in response:
                    data = f"<iq i='{sid}-2' t='get'><query xmlns='todus:gurl' url='{url}'></query></iq>"
                    ssl_socket.send(data.encode())
                    continue

                if (
                    f"t='result' i='{sid}-2'>" in response
                    and "status='200'" in response
                ):
                    match = re.match(".*du='(.*)' stat.*", response)
                    assert match, f"Unexpected response: {response}"
                    return match.group(1).replace("amp;", "")

                if "<not-authorized/>" in response:
                    raise TokenExpiredError()

                if not response:
                    raise EndOfStreamError()

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
            if resp.status_code == 403:
                raise AuthenticationError()
            resp.raise_for_status()
            token = "".join([c for c in resp.text if c in string.printable])
            return token

    def upload_file(self, token: str, data: bytes, size: int = None, t: int = 1) -> str:
        """Upload data and return the download URL."""
        up_url, down_url = self._reserve_url(token, size or len(data), t)
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
        url = self._get_real_url(token, url)
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

    def upload_file(self, data: bytes, size: int = None, t: int = 1) -> str:  # noqa
        """Upload data and return the download URL."""
        assert self.token, "Token needed"
        return super().upload_file(self.token, data, size, t)

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


def _negociate_start(
    response: str, ssl_socket: ssl.SSLSocket, authstr: bytes, sid: str
) -> bool:
    if response.startswith(
        "<?xml version='1.0'?><stream:stream i='"
    ) and response.endswith("xmlns:stream='x1' f='im.todus.cu' xmlns='jc'>"):
        return True

    auth_stream = (
        "<stream:features><es xmlns='x2'><e>PLAIN</e><e>X-OAUTH2</e></es>"
        "<register xmlns='http://jabber.org/features/iq-register'/></stream:features>"
    )
    if response == auth_stream:
        ssl_socket.send(b"<ah xmlns='ah:ns' e='PLAIN'>" + authstr + b"</ah>")
        return True

    if response == "<ok xmlns='x2'/>":
        ssl_socket.send(
            b"<stream:stream xmlns='jc' o='im.todus.cu' xmlns:stream='x1' v='1.0'>"
        )
        return True

    if "<stream:features><b1 xmlns='x4'/>" in response:
        ssl_socket.send(f"<iq i='{sid}-1' t='set'><b1 xmlns='x4'></b1></iq>".encode())
        return True

    return False


def _parse_token(token: str) -> tuple:
    phone = json.loads(b64decode(token.split(".")[1]).decode())["username"]
    authstr = b64encode((chr(0) + phone + chr(0) + token).encode("utf-8"))
    return phone, authstr
