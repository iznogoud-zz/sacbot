import praw


pt = praw.Reddit("acbot")
pt.validate_on_submit = True

idx = 0
for comment in pt.subreddit("WriteStreakES").stream.comments():
    idx += 1
    print(idx, comment.id, comment.submission.title)
