from pony.orm.core import db_session, select
from botfunctions import process_comment
import logging
import praw

from threading import Thread, Event


from prawcore.exceptions import RequestException

from acbotdb import Configuration


from config import UPDATE_TIMEOUT


class ACBotThread(Thread):
    def __init__(self, subreddit) -> None:
        super().__init__()
        self.log = logging.getLogger("acbot")
        self.reddit = praw.Reddit("acbot")
        self.reddit.validate_on_submit = True
        self.conf = select(c for c in Configuration if c.subreddit == subreddit)[:][0]
        self.name = subreddit
        self._stop_th = Event()
        self.log.info(f"Creating thread: {self.conf.subreddit}")

    def stop(self):
        self.log.info(f"Thread [{self.name}] stopping.")
        self._stop_th.set()

    def run(self) -> None:
        self.log.info(f"Starting thread: {self.conf.subreddit}")
        while not self._stop_th.is_set():
            self.check_comments()

    @db_session
    def update_conf(self):
        self.conf = select(c for c in Configuration if c.subreddit == self.name)[:][0]

    def check_comments(self):
        try:
            for comment in self.reddit.subreddit(self.conf.subreddit).stream.comments(pause_after=0):
                if comment is None:
                    if not self._stop_th.is_set():
                        self.log.info(f"Thread [{self.name}] sleeping {UPDATE_TIMEOUT} sec.")
                        self._stop_th.wait(UPDATE_TIMEOUT)
                    else:
                        break
                elif comment.is_root:
                    if "streak" in comment.submission.title.lower():
                        if hasattr(comment.submission, "link_flair_template_id"):
                            if comment.submission.link_flair_template_id == self.conf.corrected_flair_id:
                                self.log.debug(
                                    f"Submission [{comment.submission.id}] already corrected. Ignoring [{comment.id}]"
                                )
                            else:
                                process_comment(comment, self.conf)
                        else:
                            process_comment(comment, self.conf)
        except RequestException as e:
            self.log.warning(e)
