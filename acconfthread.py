from acbotsubthread import ACBotSubThread
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

                for _, th in self.bot_threads.items():
                    th[0].update_conf()
                    th[1].update_conf()

                self.redis.set("refresh-config", "False")

            self._stop_th.wait(2)

    def start_threads(self):
        with db_session:
            _temp_conf = select(c for c in Configuration)[:]
            for c in _temp_conf:
                th = ACBotThread(c.subreddit)
                th.start()
                th_sub = ACBotSubThread(c.subreddit)
                th_sub.start()
                self.bot_threads.update({c.subreddit: [th, th_sub]})

    def stop_threads(self):
        for th_name, th in self.bot_threads.items():
            th[0].stop()
            th[0].join()

            th[1].stop()
            th[1].join()
            self.log.info(f"Thread {th_name} terminated.")
