import logging
from acbotdb import Comment
from praw.models import Comment as RedditComment
from praw.models import Submission as RedditSubmission
from pony.orm.core import ObjectNotFound, db_session
from Levenshtein import ratio

from datetime import datetime


from config import DEFAULT_CORRECTED_THRESHOLD, DEFAULT_INVESTIGATE_THRESHOLD, UPDATE_TIMEOUT

log = logging.getLogger("acbot")


def parse_comment(template, submission, comment):
    out_str = template.replace("COMMENT_LINK", f"https://reddit.com{comment.permalink}")
    out_str = out_str.replace("SUBMISSION_LINK", submission.shortlink)
    if hasattr(submission, "author"):
        out_str = out_str.replace("SUBMISSION_AUTHOR", submission.author.name)
    if hasattr(comment, "author"):
        out_str = out_str.replace("COMMENT_AUTHOR", comment.author.name)
    return out_str


def process_comment(comment: RedditComment, conf, reprocess=False):
    action = "IGNORE"

    if (
        (not hasattr(comment, "removed") or not comment.removed)
        and comment.author is not None
        and comment.body != "[removed]"
        and comment.author.name != "todbot_pt"
    ):

        dbc = None

        if not reprocess:
            with db_session:
                try:
                    dbc = Comment[comment.id]
                except ObjectNotFound:
                    dbc = None

        if dbc is not None:
            log.debug(f"Comment: {comment.id} on {comment.subreddit.display_name} already processed.")
        else:
            log.debug(
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

            if conf.correction_threshold is not None:
                corrected_threshold = conf.correction_threshold

            if conf.investigate_threshold is not None:
                investigate_threshold = conf.investigate_threshold

            if similarity > corrected_threshold:
                action = "CORRECTED"

                log.debug(f"Comment [{comment.id}] corrects submission [{submission.id}].")

                if conf.comment != "":
                    log.debug(f"Added corrected comment to submission [{submission.id}].")
                    if conf.active:
                        try:
                            submission.reply(parse_comment(conf.comment, submission, comment))
                        except Exception as e:
                            log.error(e)

                    if conf.corrected_flair_id:
                        log.debug(f"Setting corrected flair on submission [{submission.id}].")
                        if conf.active:
                            try:
                                submission.flair.select(conf.corrected_flair_id)
                            except Exception as e:
                                log.error(e)

            elif similarity > investigate_threshold:
                action = "INVESTIGATE"

                log.debug(f"Comment [{comment.id}] should be manually verified.")

                if conf.mod_message != "":
                    log.debug(f"Sending message to moderators of {submission.subreddit.display_name}")
                    if conf.active:
                        try:
                            submission.subreddit.message(
                                "Potential correction.", parse_comment(conf.mod_message, submission, comment)
                            )
                        except Exception as e:
                            log.error(e)

            else:
                log.debug(f"Ignoring comment [{comment.id}].")

            if hasattr(submission, "author"):
                s_author = submission.author.name
            else:
                s_author = "deleted"

            if not reprocess:
                with db_session:
                    _ = Comment(
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
            else:
                with db_session:
                    Comment[comment.id].link = f"https://reddit.com{comment.permalink}"
                    Comment[comment.id].author = c_author
                    Comment[comment.id].similarity = similarity
                    Comment[comment.id].action = action
                    Comment[comment.id].date = datetime.now()
