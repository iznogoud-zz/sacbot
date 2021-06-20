from acbotdb import Configuration
from pony.orm.core import db_session, select
from acbothread import ACBotThread
import logging
from threading import Thread, Event


class ACConfThread(Thread):
    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("acbot")
        self.name = "ConfThread"
        self._stop_th = Event()
        self.bot_threads = {}

    def stop(self):
        self.log.info(f"Thread [{self.name}] stopping.")
        self._stop_th.set()

    def run(self) -> None:
        _orig_conf = {}
        while not self._stop_th.is_set():
            with db_session:
                _temp_conf = select(c for c in Configuration)[:]
                for c in _temp_conf:
                    if c.subreddit not in self.bot_threads:
                        th = ACBotThread(c)
                        self.bot_threads.update({c.subreddit: th})
                    else:
                        _o_conf = _orig_conf[c.subreddit]
                        if (
                            _o_conf.corrected_flair_id != c.corrected_flair_id
                            or _o_conf.comment != c.comment
                            or _o_conf.mod_message != c.mod_message
                            or _o_conf.correction_threshold != c.correction_threshold
                            or _o_conf.investigate_threshold != c.investigate_threshold
                        ):
                            self.bot_threads[c.subreddit].stop()

                            th = ACBotThread(c)
                            self.bot_threads.update({c.subreddit: th})
