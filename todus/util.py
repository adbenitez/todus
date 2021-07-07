import multiprocessing
import queue
import random
import string
from multiprocessing import Queue

from .errors import AbortError


class ResultProcess(multiprocessing.Process):
    def __init__(self, target, **kwargs) -> None:
        self._real_target = target
        self._result_queue: Queue = Queue()
        self._failed = multiprocessing.Event()
        kwargs.setdefault("daemon", True)
        super(ResultProcess, self).__init__(target=self._wrapper, **kwargs)

    def _wrapper(self, *args, **kwargs) -> None:
        try:
            self._result_queue.put(self._real_target(*args, **kwargs))
        except BaseException as ex:
            self._failed.set()
            self._result_queue.put(ex)

    def abort(self) -> None:
        self._failed.set()
        self._result_queue.put(AbortError())

    def get_result(self, timeout: float = None):
        result = None
        try:
            result = self._result_queue.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("Operation timed out.")
        if self._failed.is_set():
            raise result
        return result


def generate_token(length: int) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))
