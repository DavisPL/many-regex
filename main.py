from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor, TimeoutError
import rure
import re
import regex
import time


class RegexLibrary(ABC):

    TIMEOUT_SECONDS = 10

    @abstractmethod
    def setup_test(self, pattern: str, input: str):
        pass

    def test(self, pattern: str, input: str):
        start_time = time.perf_counter()
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.setup_test, pattern, input)
            try:
                result = future.result(timeout=self.TIMEOUT_SECONDS)
                duration = time.perf_counter() - start_time
                return {
                    "library": self.__class__.__name__,
                    "result": result,
                    "time": duration,
                    "timed_out": False,
                }
            except TimeoutError:
                duration = time.perf_counter() - start_time
                return {
                    "library": self.__class__.__name__,
                    "result": None,
                    "time": duration,
                    "timed_out": True,
                }


class Rure(RegexLibrary):

    def setup_test(self, pattern: str, input: str):
        return rure.match(pattern, input)


class Re(RegexLibrary):

    def setup_test(self, pattern: str, input: str):
        return re.match(pattern, input)


class Regex(RegexLibrary):

    def setup_test(self, pattern: str, input: str):
        return regex.match(pattern, input)


if __name__ == "__main__":
    libraries = [Rure(), Re(), Regex()]

    for library in libraries:
        res = library.test("^(a+)+$", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaB")
        print(res)
