import queue
import random
import re
import string
from multiprocessing import Event, Process, Queue

from .errors import AbortError


class ResultProcess(Process):
    """A process + internal queue to get target result in other process."""

    def __init__(self, target, **kwargs) -> None:
        self._real_target = target
        self._result_queue: Queue = Queue()
        self._failed = Event()
        kwargs.setdefault("daemon", True)
        super().__init__(target=self._wrapper, **kwargs)

    def _wrapper(self, *args, **kwargs) -> None:
        try:
            self._result_queue.put(self._real_target(*args, **kwargs))
        except BaseException as ex:
            self._failed.set()
            self._result_queue.put(ex)

    def abort(self) -> None:
        """Cancel process execution."""
        self.kill()
        self._failed.set()
        self._result_queue.put(AbortError())

    def get_result(self, timeout: float = None, kill: bool = True):
        """Return target result."""
        try:
            result = self._result_queue.get(timeout=timeout)
        except queue.Empty as ex:
            if kill:
                self.kill()
            raise TimeoutError("Operation timed out.") from ex
        if self._failed.is_set():
            raise result
        return result


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
