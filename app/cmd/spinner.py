from __future__ import annotations
import itertools
import sys
import threading
import time
from typing import Optional


# spinner shown on stdout while a block of code runs.
class Spinner:
    def __init__(self, message: str = "Processing") -> None:
        self._message = message
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _spin(self) -> None:
        for char in itertools.cycle("|/-\\"):
            if self._stop_event.is_set():
                break
            sys.stdout.write(f"\r{self._message}... {char}")
            sys.stdout.flush()
            time.sleep(0.1)
        # clear the line when done
        sys.stdout.write("\r" + " " * (len(self._message) + 10) + "\r")
        sys.stdout.flush()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()