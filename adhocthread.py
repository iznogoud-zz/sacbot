from botfunctions import process_comment
import praw
from acbotdb import Comment, Configuration
from pony.orm.core import db_session, select, set_sql_debug
from redis import Redis
from threading import Thread, Event
import logging


class AdHocThread(Thread):
    def __init__(self) -> None:
        super().__init__()
        self.log = logging.getLogger("acbot")
        self.name = "AdHocThread"
        self.redis = Redis()
        self.reddit = praw.Reddit("acbot")
        self.reddit.validate_on_submit = True

        self._stop_th = Event()

    def stop(self):
        self.log.info(f"Thread [{self.name}] stopping.")
        self._stop_th.set()

    @db_session
    def reprocess_sub(self, sub):
        self.log.info(f"Forcing the reprocessing of subreddit [{sub}]")
        _conf = select(c for c in Configuration if c.subreddit == sub)[:][0]
        _items_to_process = select(c for c in Comment if c.subreddit == sub)[:]

        for _item in _items_to_process:
            _c = self.reddit.comment(_item.id)
            process_comment(_c, _conf, reprocess=True)

    @db_session
    def process_submission(self, subid):
        self.log.info(f"Forcing the processing of submission [{subid}]")
        _submission = self.reddit.submission(subid)
        _conf = select(c for c in Configuration if c.subreddit == _submission.subreddit.display_name)[:][0]
        _items_to_process = _submission.comments

        for _item in _items_to_process:
            _c = self.reddit.comment(_item.id)
            process_comment(_c, _conf)

    def run(self) -> None:
        while not self._stop_th.is_set():
            sub = self.redis.get("reprocess-sub")

            if sub is not None:
                sub = sub.decode()
                if sub != "":
                    self.reprocess_sub(sub)
                    self.redis.set("reprocess-sub", "")

            sub = self.redis.get("process-submission")

            if sub is not None:
                sub = sub.decode()
                if sub != "":
                    self.process_submission(sub)
                    self.redis.set("process-submission", "")

            self._stop_th.wait(2)
