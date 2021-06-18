from pony.orm import *
from datetime import date, datetime, timedelta
from decimal import Decimal

from config import DATABASE_FILE, DEFAULT_CORRECTED_THRESHOLD, DEFAULT_INVESTIGATE_THRESHOLD

acbotdb = Database("sqlite", DATABASE_FILE, create_db=True)


class Comment(acbotdb.Entity):
    id = PrimaryKey(str, auto=False)
    link = Required(str)
    author = Required(str)
    similarity = Required(Decimal)
    action = Required(str)
    date = Required(datetime)
    submission_id = Required(str)
    submission_title = Required(str)
    submission_link = Required(str)
    submission_author = Required(str)
    subreddit = Required(str)


class Configuration(acbotdb.Entity):
    subreddit = Required(str)
    corrected_flair_id = Optional(str)
    comment = Optional(str)
    mod_message = Optional(str)
    correction_threshold = Optional(Decimal)
    investigate_threshold = Optional(Decimal)
    active = Required(bool)


class Defaults(acbotdb.Entity):
    correction_threshold = Required(Decimal)
    investigate_threshold = Required(Decimal)
    bot_period = Required(Decimal)


class Users(acbotdb.Entity):
    username = Required(str)
    password = Required(str)


# sql_debug(True)

acbotdb.generate_mapping(create_tables=True)


@db_session
def populate():
    if len(select(d for d in Defaults)[:]) == 0:
        default_conf = Defaults(correction_threshold=0.35, investigate_threshold=0.2, bot_period=600)


populate()


@db_session
def add_new_configuration():
    conf = Configuration(
        subreddit="Please Change",
        correction_threshold=DEFAULT_CORRECTED_THRESHOLD,
        investigate_threshold=DEFAULT_INVESTIGATE_THRESHOLD,
        active=False,
    )


@db_session
def save_configuration():
    pass


def get_data(year, month, day):
    with db_session:
        data = select(
            (
                c.submission_title,
                c.submission_link,
                c.submission_author,
                c.link,
                c.author,
                c.similarity,
                c.action,
                c.subreddit,
                c.date,
            )
            for c in Comment
            if c.date == datetime(year, month, day)
        ).order_by(-9)[:]
        return data


def get_sr_data(subreddit):
    with db_session:
        data = select(
            (
                c.submission_title,
                c.submission_link,
                c.submission_author,
                c.link,
                c.author,
                c.similarity,
                c.action,
                c.subreddit,
                c.date,
            )
            for c in Comment
            if c.subreddit == subreddit
        ).order_by(-9)[:]
        return data


def get_last_24h():
    with db_session:
        data = select(
            (
                c.submission_title,
                c.submission_link,
                c.submission_author,
                c.link,
                c.author,
                c.similarity,
                c.action,
                c.subreddit,
                c.date,
            )
            for c in Comment
            if c.date >= (datetime.now() - timedelta(days=1))
        ).order_by(-9)[:]
        return data
