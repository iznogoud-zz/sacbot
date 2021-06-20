from acbothread import ACBotThread
from acbotdb import Configuration
import logging
import signal

from pony.orm.core import db_session, select

from config import DEFAULT_CORRECTED_THRESHOLD, DEFAULT_INVESTIGATE_THRESHOLD, UPDATE_TIMEOUT, DATABASE_FILE


def setup_log():
    logger = logging.getLogger("acbot")
    formatter = logging.Formatter("%(asctime)s | %(name)s |  %(levelname)s | %(message)s")
    logger.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(formatter)

    # logFilePath = "acbot.log"
    # file_handler = logging.handlers.TimedRotatingFileHandler(
    #     filename=logFilePath, when='midnight', backupCount=30)
    # file_handler.setFormatter(formatter)
    # file_handler.setLevel(logging.DEBUG)

    # logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


stop_bot = False
bot_threads = []


def sigterm_handler(_signo, _stack_frame):
    log = logging.getLogger("acbot")
    log.info("Shutting down")

    for th in bot_threads:
        th.stop()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, sigterm_handler)
    signal.signal(signal.SIGTERM, sigterm_handler)
    setup_log()

    with db_session:
        for c in select(c for c in Configuration)[:]:
            th = ACBotThread(c)
            th.start()
            bot_threads.append(th)

    for th in bot_threads:
        th.join()
