from pony.orm.core import db_session, select
from botfunctions import process_comment
import logging
import praw
import re
from datetime import date


from threading import Thread, Event


from prawcore.exceptions import RequestException

from acbotdb import Configuration, Streaks


from config import UPDATE_TIMEOUT


class ACBotSubThread(Thread):
    def __init__(self, subreddit) -> None:
        super().__init__()
        self.log = logging.getLogger("acbot")
        self.reddit = praw.Reddit("acbot")
        self.reddit.validate_on_submit = True
        self.conf = select(c for c in Configuration if c.subreddit == subreddit)[:][0]
        self.name = "Submission" + subreddit
        self._stop_th = Event()
        self.log.info(f"Creating submission thread: {self.name}")

    def stop(self):
        self.log.info(f"Thread [{self.name}] stopping.")
        self._stop_th.set()

    def run(self) -> None:
        self.log.info(f"Starting thread: {self.name}")
        while not self._stop_th.is_set():
            self.check_subs()

    @db_session
    def update_conf(self):
        self.conf = select(c for c in Configuration if c.subreddit == self.name)[:][0]

    def check_subs(self):
        try:
            for sub in self.reddit.subreddit(self.conf.subreddit).stream.submissions(pause_after=0):
                if sub is None:
                    if not self._stop_th.is_set():
                        self.log.info(f"Thread [{self.name}] sleeping {UPDATE_TIMEOUT} sec.")
                        self._stop_th.wait(UPDATE_TIMEOUT)
                    else:
                        break
                else:
                    user = sub.author.name
                    sr = self.conf.subreddit
                    s_date = date.fromtimestamp(sub.created_utc)
                    streak = re.match("(?:^Streak|^streak)\s+(\d+).*", sub.title)

                    if streak is not None:

                        with db_session:
                            submitter = select(c for c in Streaks if c.username == user and c.subreddit == sr)[:]

                            if len(submitter) == 0:
                                _ = Streaks(
                                    username=user,
                                    subreddit=sr,
                                    date=s_date.strftime("%Y/%m/%d"),
                                    streak=streak.groups()[0],
                                )
                                self.log.info(
                                    f"New user added: {sub.title}, {user}, {sr}, {s_date}, {streak.groups()[0]}"
                                )
                            else:
                                time_since_last_sub = s_date - submitter[0].date
                                if time_since_last_sub.days > 1:
                                    submitter[0].streak = 1
                                    self.log.info(f"Setting streak to 1 for user {user} in {sr} [{sub.title}]")
                                elif time_since_last_sub.days == 1:
                                    submitter[0].streak = streak.groups()[0]
                                    submitter[0].date = s_date.strftime("%Y/%m/%d")
                                    self.log.info(
                                        f"Setting streak to {streak.groups()[0]} for user {user} in {sr} [{sub.title}]"
                                    )

                    # if "streak" in comment.submission.title.lower():
                    #     if hasattr(comment.submission, "link_flair_template_id"):
                    #         if comment.submission.link_flair_template_id == self.conf.corrected_flair_id:
                    #             self.log.debug(
                    #                 f"Submission [{comment.submission.id}] already corrected. Ignoring [{comment.id}]"
                    #             )
                    #         else:
                    #             process_comment(comment, self.conf)
                    #     else:
                    #         process_comment(comment, self.conf)
        except Exception as e:
            self.log.warning(e)
