from datetime import datetime
from difflib import SequenceMatcher

from prawcore.auth import TrustedAuthenticator
from acbotdb import Comment, Configuration
import logging
import time
import signal
from threading import Thread
import threading
from praw.models import Comment as RedditComment
from praw.models import Submission as RedditSubmission
from pony.orm.core import ObjectNotFound, db_session, select

import praw

from acbotfunctions import comment_already_processed, get_submissions, md_to_text, parse_comment, setup_log
from config import DEFAULT_CORRECTED_THRESHOLD, DEFAULT_INVESTIGATE_THRESHOLD, UPDATE_TIMEOUT, DATABASE_FILE


class ACBotThread(Thread):
    def __init__(self, conf: Configuration) -> None:
        super().__init__()
        self.log = logging.getLogger("acbot")
        self.reddit = praw.Reddit("acbot")
        self.reddit.validate_on_submit = True
        self.conf = conf
        self.name = conf.subreddit
        self._stop_th = threading.Event()

    def stop(self):
        self.log.info(f"Thread [{self.name}] stopping.")
        self._stop_th.set()

    def run(self) -> None:
        for comment in self.reddit.subreddit(self.conf.subreddit).stream.comments(pause_after=0):
            if comment is None:
                self.log.info(f"Thread [{self.name}] sleeping {UPDATE_TIMEOUT} sec.")
                self._stop_th.wait(UPDATE_TIMEOUT)
            elif comment.is_root:
                if hasattr(comment.submission, "link_flair_template_id"):
                    if comment.submission.link_flair_template_id == self.conf.corrected_flair_id:
                        self.log.debug(
                            f"Submission [{comment.submission.id}] already corrected. Ignoring [{comment.id}]"
                        )
                    else:
                        self.process_comment(comment)
                else:
                    self.process_comment(comment)

            if self._stop_th.is_set():
                break

    def process_comment(self, comment: RedditComment):
        action = "IGNORE"
        if not hasattr(comment, "removed") or not comment.removed:
            dbc = None
            with db_session:
                try:
                    dbc = Comment[comment.id]
                except ObjectNotFound:
                    dbc = None

            if dbc is not None:
                self.log.debug(f"Comment: {comment.id} on {comment.subreddit.display_name} already processed.")
            else:
                self.log.debug(
                    f"{comment.subreddit.display_name}:: Processing comment [{comment.id}] at https://reddit.com{comment.permalink}."
                )

                submission: RedditSubmission = comment.submission

                similarity = SequenceMatcher(None, md_to_text(submission.selftext), md_to_text(comment.body)).ratio()

                if hasattr(comment, "author"):
                    c_author = comment.author.name
                else:
                    c_author = "deleted"

                corrected_threshold = DEFAULT_CORRECTED_THRESHOLD
                investigate_threshold = DEFAULT_INVESTIGATE_THRESHOLD

                if self.conf.correction_threshold is not None:
                    corrected_threshold = self.conf.correction_threshold

                if self.conf.investigate_threshold is not None:
                    investigate_threshold = self.conf.investigate_threshold

                if similarity > corrected_threshold:
                    action = "CORRECTED"

                    self.log.debug(f"Comment [{comment.id}] corrects submission [{submission.id}].")

                    if self.conf.comment != "":
                        self.log.debug(f"Added correctes comment to submission [{submission.id}].")
                        # submission.reply(parse_comment(self.conf.comment, submission, comment))

                        if self.conf.corrected_flair_id:
                            self.log.debug(f"Setting corrected flair on submission [{submission.id}].")
                            # submission.flair.select(self.conf.corrected_flair_id)

                elif similarity > investigate_threshold:
                    action = "INVESTIGATE"

                    self.log.debug(f"Comment [{comment.id}] should be manually verified.")

                    if self.conf.mod_message != "":
                        self.log.debug(f"Sending message to moderators of {submission.subreddit.display_name}")
                        # submission.subreddit.message(
                        #     "Potential correction.", parse_comment(self.conf.mod_message, submission, comment)
                        # )

                else:
                    self.log.debug(f"Ignoring comment [{comment.id}].")

                if hasattr(submission, "author"):
                    s_author = submission.author.name
                else:
                    s_author = "deleted"

                with db_session:
                    nc = Comment(
                        id=comment.id,
                        link=f"https://reddit.com{comment.permalink}",
                        author=c_author,
                        similarity=similarity,
                        action=action,
                        date=datetime.now(),
                        submission_id=submission.id,
                        submission_title=submission.title,
                        submission_link=submission.shortlink,
                        submission_author=s_author,
                        subreddit=submission.subreddit.display_name,
                    )


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
