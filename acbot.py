import logging
import os
import signal
from threading import Thread
import threading
import time

from acbotfunctions import get_submissions, setup_log
from config import UPDATE_TIMEOUT, DATABASE_FILE


class acbotthread(Thread):
    def __init__(self) -> None:
        self._stop_th = threading.Event()
        super().__init__()

    def stop(self):
        self._stop_th.set()

    def run(self) -> None:
        while not self._stop_th.is_set():
            get_submissions()
            self._stop_th.wait(UPDATE_TIMEOUT)


stop_bot = False
bot_thread = acbotthread()


def sigterm_handler(_signo, _stack_frame):
    log = logging.getLogger("acbot")
    log.info("Shutting down")
    bot_thread.stop()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)
    setup_log()

    bot_thread.start()
    bot_thread.join()
