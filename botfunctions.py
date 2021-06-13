from logging.handlers import TimedRotatingFileHandler
import sqlite3
from sqlite3 import Error
from datetime import datetime
from difflib import SequenceMatcher

import praw
import yaml
import logging

DEFAULT_CORRECTED_THRESHOLD = 0.5
DEFAULT_INVESTIGATE_THRESHOLD = 0.2
DATABASE_FILE = "acbot.sqlite"


def setup_log():
    logger = logging.getLogger("acbot")
    formatter = logging.Formatter('%(asctime)s | %(name)s |  %(levelname)s | %(message)s')
    logger.setLevel(logging.DEBUG)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(formatter)

    logFilePath = "acbot.log"
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=logFilePath, when='midnight', backupCount=30)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def create_database(db_file: str):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print("Could not open or create the database at: " + db_file)

    c = conn.cursor()

    c.execute("create table submissions ([id] integer primary key, [subreddit] text, [submission_id] text, "
              "[submission_title] text, [submission_link] text, [submission_author] text, [comment_id] text, "
              "[comment_link] text, [comment_author] text, [similarity] real, [action] text, [action_date] text)")

    conn.commit()
    conn.close()

def open_db_connection(name = DATABASE_FILE):
    log = logging.getLogger("acbot")
    bot_db = None
    try:
        bot_db = sqlite3.connect(DATABASE_FILE)
    except Error as e:
        log.error("Could not open or create the database at: " + DATABASE_FILE)
        return None

    return bot_db

def comment_already_processed(sub_id, comment_id):
    bot_db = open_db_connection()

    exists = bot_db.cursor().execute(f"SELECT EXISTS(SELECT 1 FROM SUBMISSIONS WHERE  submission_id = "
                                   f"'{sub_id}' and comment_id = '{comment_id}');").fetchall()

    bot_db.close()

    return exists[0][0] == 1

def insert_submission(sr_name, sub_id, sub_title, sub_link, sub_author, comment_id, comment_link, comment_author,
                      similarity,
                      action):
    bot_db = open_db_connection()
    c = bot_db.cursor()
    log = logging.getLogger("acbot")
    log.info(f"Submission {sub_id} on subreddit {sr_name} marked as {action}.")
    log.debug((f"{sr_name}, {sub_id}, {sub_title}, {sub_link}, {sub_author}, {comment_id}, {comment_link}, "
              f"{comment_author}, {similarity}, {action}, {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))

    insert_string = (f'insert into submissions (subreddit, submission_id, submission_title, submission_link, '
              f'submission_author, comment_id, comment_link, comment_author, similarity, action, action_date) ' 
              f'values ("{sr_name}", "{sub_id}", "{sub_title}", "{sub_link}", "{sub_author}", "{comment_id}", '
              f'"{comment_link}", "{comment_author}", "{similarity*100:.2f}", "{action}", "'
              f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")')

    c.execute(insert_string)
    bot_db.commit()
    bot_db.close()


def parse_comment(template, submission, comment):
    out_str = template.replace("COMMENT_LINK", f"https://reddit.com{comment.permalink}")
    out_str = out_str.replace("SUBMISSION_LINK", submission.shortlink)
    if hasattr(submission, "author"):
        out_str = out_str.replace("SUBMISSION_AUTHOR", submission.author.name)
    if hasattr(comment, "author"):
        out_str = out_str.replace("COMMENT_AUTHOR", comment.author.name)
    return out_str


def check_submissions():
    log = logging.getLogger("acbot")

    pt = praw.Reddit("acbot")
    pt.validate_on_submit = True

    yaml_conf = None
    try:
        yaml_conf = yaml.safe_load(open("config.yaml", "r"))
    except yaml.YAMLError as exc:
        log.error(exc)
        return None

    for sr_name, sr_conf in yaml_conf.items():
        log.info(f"Processing {sr_name}")
        idx = 1
        submissions = []
        for s in pt.subreddit(sr_name).search(query=f"title:Streak", sort="new", time_filter="week", limit=None):
            if "corrected_flair_id" in sr_conf:
                if hasattr(s, "link_flair_template_id") and s.link_flair_template_id != sr_conf["corrected_flair_id"]:
                    submissions.append(s)
            else:
                submissions.append(s)

        for s in submissions:
            log.debug(f"{sr_name} processing {idx}/{len(submissions)} {s.shortlink}")
            idx += 1
            s_text = s.selftext
            if hasattr(s, "author"):
                s_author = s.author.name
            else:
                s_author = "deleted"

            for c in s.comments:
                action = "IGNORE"
                if not hasattr(c, "removed") or not c.removed:
                    if comment_already_processed(s.id, c.id):
                        log.debug(f"Comment: https://reddit.com{c.permalink} already processed.")
                    else:
                        log.debug(f"Processing comment https://reddit.com{c.permalink}.")
                        c_text = c.body

                        similarity = SequenceMatcher(None, s_text, c_text).ratio()

                        if hasattr(c, "author"):
                            c_author = c.author.name
                        else:
                            c_author = "deleted"

                        corrected_threshold = DEFAULT_CORRECTED_THRESHOLD
                        investigate_threshold = DEFAULT_INVESTIGATE_THRESHOLD

                        if "similarity_correction_threshold" in sr_conf:
                            corrected_threshold = sr_conf["similarity_correction_threshold"]

                        if "similarity_investigate_threshold" in sr_conf:
                            investigate_threshold = sr_conf["similarity_investigate_threshold"]

                        if similarity > corrected_threshold:
                            action = "CORRECTED"

                            if "bot_comment" in sr_conf:
                                log.debug(f"Commenting that the submission was marked as correct.")
                                s.reply(parse_comment(sr_conf["bot_comment"], s, c))

                                if "corrected_flair_id" in sr_conf:
                                    log.debug(f"Setting corrected flair.")
                                    s.flair.select(sr_conf["corrected_flair_id"])

                        elif similarity > investigate_threshold:
                            action = "INVESTIGATE"

                            if "mod_team_message" in sr_conf:
                                log.debug(f"Sending message to moderators of {sr_name}")
                                s.subreddit.message("Potential correction.", parse_comment(sr_conf[
                                                                                               "mod_team_message"], s, c))

                        insert_submission(sr_name, s.id,  s.title, s.shortlink, s_author, c.id,
                                          f"https://reddit.com{c.permalink}", c_author,
                                          similarity, action)