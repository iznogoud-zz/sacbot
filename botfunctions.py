from datetime import date
from difflib import SequenceMatcher

import praw
import yaml

DEFAULT_CORRECTED_THRESHOLD = 0.15
DEFAULT_INVESTIGATE_THRESHOLD = 0.04


def parse_comment(template, submission, comment):
    out_str = template.replace("COMMENT_LINK", f"https://reddit.com{comment.permalink}")
    out_str = out_str.replace("SUBMISSION_LINK",submission.shortlink)
    out_str = out_str.replace("SUBMISSION_LINK", submission.shortlink)
    if hasattr(submission, "author"):
        out_str = out_str.replace("SUBMISSION_AUTHOR", submission.author.name)
    if hasattr(comment, "author"):
        out_str = out_str.replace("SUBMISSION_AUTHOR", comment.author.name)
    return out_str


def check_submissions():
    pt = praw.Reddit("acbot")
    pt.validate_on_submit = True

    yaml_conf = None
    try:
        yaml_conf = yaml.safe_load(open("config.yaml", "r"))
    except yaml.YAMLError as exc:
        print(exc)

    results = []

    for sr_name, sr_conf in yaml_conf.items():
        print(sr_name)
        idx = 1
        submissions = []
        for s in pt.subreddit(sr_name).search(query=f"title:Streak", sort="new", time_filter="day", limit=None):
            if "to_be_corrected_flair_id" in sr_conf:
                if hasattr(s, "link_flair_template_id") and s.link_flair_template_id == sr_conf["to_be_corrected_flair_id"]:
                    submissions.append(s)
            else:
                submissions.append(s)

        for s in submissions:
            print(f"{sr_name} processing {idx}/{len(submissions)} {s.shortlink}")
            idx += 1
            s_text = s.selftext
            if hasattr(s, "author"):
                s_author = s.author.name
            else:
                s_author = "deleted"

            for c in s.comments:
                if not hasattr(c, "removed") or not c.removed:
                    c_text = c.body

                    similarity = SequenceMatcher(None, s_text, c_text).ratio()

                    if hasattr(c, "author"):
                        author = c.author.name
                    else:
                        author = "deleted"

                    if "similarity_correction_threshold" in sr_conf and similarity > sr_conf[
                        "similarity_correction_threshold"] or similarity > DEFAULT_CORRECTED_THRESHOLD:
                        action = "MARK_CORRECTED"

                        if "bot_comment" in sr_conf:
                            s.reply(sr_conf["bot_comment"])

                        if "corrected_flair_id" in sr_conf:
                            s.flair.select(sr_conf["corrected_flair_id"])

                    elif "similarity_investigate_threshold" in sr_conf and similarity > sr_conf[
                        "similarity_investigate_threshold"] or similarity > DEFAULT_INVESTIGATE_THRESHOLD:
                        action = "INVESTIGATE"

                        if "mod_team_message" in sr_conf:
                            s.subreddit.message("Potential correction.", parse_comment(sr_conf[
                                "mod_team_message"], s, c))
                    else:
                        action = "IGNORE"

                    if action != "IGNORE":
                        res = [
                            s.title,
                            s.shortlink,
                            s_author,
                            f"https://reddit.com{c.permalink}",
                            author,
                            f"{similarity * 100:.2f}",
                            action,
                            sr_name,
                        ]

                        print(res)
                        results.append(
                            res
                        )

                    if action == "MARK_CORRECTED":
                        break  # Found one comment that corrects this submission

    filename = f"bot-results-{date.today().strftime('%Y.%m.%d')}.log"
    with open(filename, "a") as results_file:
        for l in results:
            results_file.write(f"{';'.join(e for e in l)}\n")

    return results
