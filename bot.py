import os
import signal
import time

from botfunctions import check_submissions, create_database, DATABASE_FILE, setup_log

UPDATE_TIMEOUT = 600

stop_bot = False


def sigterm_handler(_signo, _stack_frame):
    print("Shutting down")
    global stop_bot
    stop_bot = True


if __name__ == '__main__':
    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)
    setup_log()
    if not os.path.isfile(DATABASE_FILE):
        create_database(DATABASE_FILE)

    while not stop_bot:
        check_submissions()
        time.sleep(UPDATE_TIMEOUT)
