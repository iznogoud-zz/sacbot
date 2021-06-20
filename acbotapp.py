import os
from datetime import date
from decimal import Decimal

from flask import Flask, render_template, redirect, request
from pony.orm import db_session
from pony.orm.core import select

from acbotdb import get_data, get_last_24h, get_sr_data, populate, add_new_configuration, Configuration, acbotdb
from config import DATABASE_FILE

app = Flask(__name__)


# def get_data(year, month, day):
#     bot_db = open_db_connection()
#     sel_str = (
#         f"select submission_title, submission_link, submission_author, comment_link, comment_author, similarity, "
#         f"action, subreddit, action_date from submissions where "
#         f"date(action_date) = date(\"{year:02}-{month:02}-{day:02}\")")
#
#     db_data = bot_db.cursor().execute(sel_str).fetchall()
#
#     bot_db.close()
#     return [list(l) for l in db_data]


@app.route("/")
def acbot_today():
    today = date.today()
    return render_template("submissions.html", my_list=get_last_24h())


@app.route("/<subreddit>")
def acbot_sr(subreddit):
    return render_template("submissions.html", my_list=get_sr_data(subreddit))


@app.route("/<year>/<month>/<day>")
def acbot_date(year, month, day):
    return render_template("submissions.html", my_list=get_data(int(year), int(month), int(day)))


@app.route("/config")
@db_session
def acbot_config():
    configs = select(
        (
            c.id,
            c.subreddit,
            c.corrected_flair_id,
            c.comment,
            c.mod_message,
            c.correction_threshold,
            c.investigate_threshold,
            c.active,
        )
        for c in Configuration
    )[:]
    return render_template("config.html", sr_list=configs)


@app.route("/new_conf")
def acbot_new_conf():
    add_new_configuration()
    return redirect("/config")


@app.route("/save_conf", methods=["POST"])
@db_session
def acbot_save_conf():

    for c in select(c for c in Configuration)[:]:
        c.active = False

    for name, val in request.form.items():
        f_name, c_idx = name.split("-")
        if f_name == "del" and val == "true":
            Configuration[c_idx].delete()
        else:
            Configuration[c_idx].set(**{f_name: val})
    return redirect("/config")


if __name__ == "__main__":
    # if not os.path.isfile(DATABASE_FILE):
    #     acbotdb.generate_mapping(create_tables=True)
    #     populate()
    # else:
    #     acbotdb.generate_mapping()
    app.run()
