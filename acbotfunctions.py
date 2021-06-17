from logging.handlers import TimedRotatingFileHandler
from re import sub
import markdown
from bs4 import BeautifulSoup
from sqlite3 import Error
from datetime import datetime
from difflib import SequenceMatcher

from pony.orm.core import ObjectNotFound, select
from acbotdb import Comment, Configuration
from pony.orm import db_session


import praw
import yaml
import logging

from config import DATABASE_FILE, DEFAULT_CORRECTED_THRESHOLD, DEFAULT_INVESTIGATE_THRESHOLD

log = logging.getLogger("acbot")


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


@db_session
def comment_already_processed(comment_id):
    c = Comment(id == comment_id)

    return c is not None


def md_to_text(md):
    html = markdown.markdown(md)
    soup = BeautifulSoup(html, features="html.parser")
    return soup.get_text()


def parse_comment(template, submission, comment):
    out_str = template.replace("COMMENT_LINK", f"https://reddit.com{comment.permalink}")
    out_str = out_str.replace("SUBMISSION_LINK", submission.shortlink)
    if hasattr(submission, "author"):
        out_str = out_str.replace("SUBMISSION_AUTHOR", submission.author.name)
    if hasattr(comment, "author"):
        out_str = out_str.replace("COMMENT_AUTHOR", comment.author.name)
    return out_str


def get_submissions(reddit, subreddit):

    sr_conf = None
    with db_session:
        sr_conf = select(c for c in Configuration if c.subreddit == subreddit)[:]

    for conf in sr_conf:

        processed_subs = 0
        no_comments = 0
        total_subs = 0
        corrected = 0

        subs = pt.subreddit(conf.subreddit).search(query=f"title:Streak", sort="hot", time_filter="day", limit=None)

        for s in subs:
            total_subs += 1
            if s.num_comments > 0:
                if conf.corrected_flair_id != "":
                    # log.info(f"Processing {s.title} {s.shortlink}")
                    if hasattr(s, "link_flair_template_id"):
                        if s.link_flair_template_id != conf.corrected_flair_id:
                            process_submission(s)
                            processed_subs += 1
                        else:
                            corrected += 1
                    else:
                        process_submission(s)
                        processed_subs += 1
                else:
                    process_submission(s)
                    processed_subs += 1
            else:
                no_comments += 1

        log.info(
            f"Processed {processed_subs} submissions of {total_subs} ({no_comments} had no comments) ({corrected} were corrected)in {conf.subreddit}"
        )


def process_submission(s):

    idx = 0
    log.debug(f"Processing {s.title} {s.shortlink}")
    idx += 1
    s_text = s.selftext
    if hasattr(s, "author"):
        s_author = s.author.name
    else:
        s_author = "deleted"

    correction_authors = []

    for c in s.comments:
        action = "IGNORE"
        if not hasattr(c, "removed") or not c.removed:
            dbc = None
            with db_session:
                try:
                    dbc = Comment[c.id]
                except ObjectNotFound:
                    dbc = None

            if dbc is not None:
                log.debug(f"Comment: https://reddit.com{c.permalink} already processed.")
            else:
                log.debug(f"Processing comment https://reddit.com{c.permalink}.")
                c_text = c.body

                similarity = SequenceMatcher(None, md_to_text(s_text), md_to_text(c_text)).ratio()

                if hasattr(c, "author"):
                    c_author = c.author.name
                else:
                    c_author = "deleted"

                corrected_threshold = DEFAULT_CORRECTED_THRESHOLD
                investigate_threshold = DEFAULT_INVESTIGATE_THRESHOLD

                sr_conf = None
                with db_session:
                    sr_conf = select(c for c in Configuration if c.subreddit == s.subreddit.display_name)[:][0]

                if sr_conf.correction_threshold is not None:
                    corrected_threshold = sr_conf.correction_threshold

                if sr_conf.investigate_threshold is not None:
                    investigate_threshold = sr_conf.investigate_threshold

                if similarity > corrected_threshold:
                    action = "CORRECTED"

                    correction_authors.append(c_author)

                    if sr_conf.comment != "":
                        log.debug(f"Commenting that the submission was marked as correct.")
                        s.reply(parse_comment(sr_conf.comment, s, c))

                        if sr_conf.corrected_flair_id:
                            log.debug(f"Setting corrected flair.")
                            s.flair.select(sr_conf.corrected_flair_id)

                elif similarity > investigate_threshold:
                    action = "INVESTIGATE"

                    if sr_conf.mod_message != "":
                        log.debug(f"Sending message to moderators of {s.subreddit.display_name}")
                        s.subreddit.message("Potential correction.", parse_comment(sr_conf.mod_message, s, c))

                with db_session:
                    nc = Comment(
                        id=c.id,
                        link=f"https://reddit.com{c.permalink}",
                        author=c_author,
                        similarity=similarity,
                        action=action,
                        date=datetime.now(),
                        submission_id=s.id,
                        submission_title=s.title,
                        submission_link=s.shortlink,
                        submission_author=s_author,
                        subreddit=s.subreddit.display_name,
                    )
