from acbotdb import Configuration
from pony.orm.core import db_session, select
from acbothread import ACBotThread
import logging
from redis import Redis
from threading import Thread, Event


class ACConfThread(Thread):
    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("acbot")
        self.name = "ConfThread"
        self.redis = Redis()
        self.redis.set("refresh-config", "False")

        self._stop_th = Event()
        self.bot_threads = {}
        self.start_threads()

    def stop(self):
        self.log.info(f"Thread [{self.name}] stopping.")
        self.stop_threads()
        self._stop_th.set()

    def run(self) -> None:
        while not self._stop_th.is_set():
            refresh_conf = self.redis.get("refresh-config")
            if refresh_conf is not None and refresh_conf.decode() == "True":
                self.log.info("New configuration. Refreshing threads.")

                self.stop_threads()
                self.start_threads()

                self.redis.set("refresh-config", "False")

            self._stop_th.wait(1)

    def start_threads(self):
        with db_session:
            _temp_conf = select(c for c in Configuration)[:]
            for c in _temp_conf:
                th = ACBotThread(c)
                th.start()
                self.bot_threads.update({c.subreddit: th})

    def stop_threads(self):
        for th_name, th in self.bot_threads.items():
            th.stop()
            th.join()
            self.log.info(f"Thread {th_name} terminated.")
