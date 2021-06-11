from datetime import date

from flask import Flask, render_template

from redis import Redis
from rq.job import Job

app = Flask(__name__)


def get_render_data():
    job = Job.fetch("praw", connection=Redis())
    return job.result

def get_data(year, month, day):
    out = []
    filename = f"bot-results-{year}.{month}.{day}.log"
    with open(filename, "r") as results_file:
        for l in results_file.readlines():
            out.append(l.split(';'))
    return out


@app.route("/")
def acbot():
    return render_template("submissions.html", my_list=get_render_data())


@app.route("/today")
def acbot_today():
    today = date.today()
    return render_template("submissions.html", my_list=get_data(today.year, today.month, today.day))


@app.route("/<year>/<month>/<day>")
def acbot_date(year, month, day):
    return render_template("submissions.html", my_list=get_data(year, month, day))


if __name__ == '__main__':
    app.run()
