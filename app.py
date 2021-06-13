from datetime import date
from flask import Flask, render_template

from botfunctions import open_db_connection

app = Flask(__name__)


def get_data(year, month, day):
    bot_db = open_db_connection()
    sel_str = (
        f"select submission_title, submission_link, submission_author, comment_link, comment_author, similarity, "
        f"action, subreddit, action_date from submissions where "
        f"date(action_date) = date(\"{year:02}-{month:02}-{day:02}\")")

    db_data = bot_db.cursor().execute(sel_str).fetchall()

    bot_db.close()
    return [list(l) for l in db_data]


@app.route("/")
def acbot_today():
    today = date.today()
    return render_template("submissions.html", my_list=get_data(today.year, today.month, today.day))


@app.route("/<year>/<month>/<day>")
def acbot_date(year, month, day):
    return render_template("submissions.html", my_list=get_data(int(year), int(month), int(day)))


if __name__ == '__main__':
    app.run()
