import string
from typing import Any, Callable

import requests

from .s3 import get_real_url, reserve_url
from .util import ResultProcess, generate_token


class ToDusClient:
    def __init__(
        self, version_name: str = "0.38.34", version_code: str = "21805"
    ) -> None:
        self.version_name = version_name
        self.version_code = version_code

        self.timeout = 60
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept-Encoding": "gzip",
            }
        )
        self._real_request = self.session.request
        self.session.request = self._request
        self._process = None

    def _request(self, *args, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        return self._real_request(*args, **kwargs)

    def _run_task(self, task: Callable, timeout: float) -> Any:
        self._process = ResultProcess(target=task)
        self._process.start()
        try:
            return self._process.get_result(timeout)
        finally:
            self.abort()

    def abort(self) -> None:
        p = self._process
        if p is not None:
            self._process = None
            p.kill()
            p.abort()

    @property
    def auth_ua(self) -> str:
        return "ToDus {} Auth".format(self.version_name)

    @property
    def upload_ua(self) -> str:
        return "ToDus {} HTTP-Upload".format(self.version_name)

    @property
    def download_ua(self) -> str:
        return "ToDus {} HTTP-Download".format(self.version_name)

    def request_code(self, phone_number: str) -> None:
        """Request server to send verification SMS code."""

        def task() -> None:
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

        self._run_task(task, self.timeout)

    def validate_code(self, phone_number: str, code: str) -> str:
        """Validate phone number with received SMS code.

        Returns the account password.
        """

        def task() -> str:
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
                else:
                    return resp.content[5:166].decode()

        return self._run_task(task, self.timeout)

    def login(self, phone_number: str, password: str) -> str:
        """Login with phone number and password to get an access token."""

        def task() -> str:
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

        return self._run_task(task, self.timeout)

    def upload_file(self, token: str, data: bytes, size: int = None) -> str:
        """Upload data and return the download URL."""
        if size is None:
            size = len(data)

        def task1() -> tuple:
            return reserve_url(token, size)

        up_url, down_url = self._run_task(task1, self.timeout)

        timeout = max(len(data) / 1024 / 1024 * 20, self.timeout)

        def task2() -> tuple:
            headers = {
                "User-Agent": self.upload_ua,
                "Authorization": "Bearer {}".format(token),
            }
            with self.session.put(
                url=up_url, data=data, headers=headers, timeout=timeout
            ) as resp:
                resp.raise_for_status()
            return down_url

        return self._run_task(task2, timeout)

    def download_file(self, token: str, url: str, path: str) -> int:
        """Download file URL.

        Returns the file size.
        """

        def task1() -> str:
            return get_real_url(token, url)

        url = self._run_task(task1, self.timeout)

        def task2() -> int:
            headers = {
                "User-Agent": self.download_ua,
                "Authorization": "Bearer {}".format(token),
            }
            with self.session.get(url=url, headers=headers) as resp:
                resp.raise_for_status()
                size = int(resp.headers.get("Content-Length"))
                with open(path, "wb") as file:
                    file.write(resp.content)
                return size

        return self._run_task(task2, self.timeout)
