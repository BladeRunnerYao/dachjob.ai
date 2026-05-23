import time
from contextlib import contextmanager


@contextmanager
def track_latency():
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed
