import logging
import praw

from threading import Thread, Event
from datetime import datetime

from praw.models import Comment as RedditComment
from praw.models import Submission as RedditSubmission
from prawcore.exceptions import RequestException

from acbotdb import Comment, Configuration

from pony.orm.core import ObjectNotFound, db_session
from Levenshtein import ratio

from config import DEFAULT_CORRECTED_THRESHOLD, DEFAULT_INVESTIGATE_THRESHOLD, UPDATE_TIMEOUT


class ACBotThread(Thread):
    def __init__(self, conf: Configuration) -> None:
        super().__init__()
        self.log = logging.getLogger("acbot")
        self.reddit = praw.Reddit("acbot")
        self.reddit.validate_on_submit = True
        self.conf = conf
        self.name = conf.subreddit
        self._stop_th = Event()
        self.log.info(f"Creating thread: {self.conf.subreddit}")

    def stop(self):
        self.log.info(f"Thread [{self.name}] stopping.")
        self._stop_th.set()

    def run(self) -> None:
        self.log.info(f"Starting thread: {self.conf.subreddit}")
        while not self._stop_th.is_set():
            self.check_comments()

    def parse_comment(self, template, submission, comment):
        out_str = template.replace("COMMENT_LINK", f"https://reddit.com{comment.permalink}")
        out_str = out_str.replace("SUBMISSION_LINK", submission.shortlink)
        if hasattr(submission, "author"):
            out_str = out_str.replace("SUBMISSION_AUTHOR", submission.author.name)
        if hasattr(comment, "author"):
            out_str = out_str.replace("COMMENT_AUTHOR", comment.author.name)
        return out_str

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
                                self.process_comment(comment)
                        else:
                            self.process_comment(comment)
        except RequestException as e:
            self.log.warning(e)

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

                similarity = ratio(submission.selftext, comment.body)

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
                        self.log.debug(f"Added corrected comment to submission [{submission.id}].")
                        if self.conf.active:
                            submission.reply(self.parse_comment(self.conf.comment, submission, comment))

                        if self.conf.corrected_flair_id:
                            self.log.debug(f"Setting corrected flair on submission [{submission.id}].")
                            if self.conf.active:
                                submission.flair.select(self.conf.corrected_flair_id)

                elif similarity > investigate_threshold:
                    action = "INVESTIGATE"

                    self.log.debug(f"Comment [{comment.id}] should be manually verified.")

                    if self.conf.mod_message != "":
                        self.log.debug(f"Sending message to moderators of {submission.subreddit.display_name}")
                        if self.conf.active:
                            submission.subreddit.message(
                                "Potential correction.", self.parse_comment(self.conf.mod_message, submission, comment)
                            )

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
