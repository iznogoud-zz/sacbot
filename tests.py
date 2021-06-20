from difflib import SequenceMatcher
from re import M
from acbotfunctions import md_to_text
import praw
from fuzzywuzzy import fuzz
from Levenshtein import ratio

pt = praw.Reddit("acbot")
pt.validate_on_submit = True

# idx = 0
# for comment in pt.subreddit("WriteStreakES").stream.comments():
#     idx += 1
#     print(idx, comment.id, comment.submission.title)
# \

s = pt.submission(id="o30g2j").selftext
c = pt.comment("h29c5ys").body

s_t = md_to_text(s)
c_t = md_to_text(c)
print(s_t)
print("----------------------------------")
print(c_t)


def withoutJunk(input, chars):
    return input.translate(str.maketrans("", "", chars))


def lam(x):
    if x in " \t":
        print(x)
        return True
    else:
        return False


print(SequenceMatcher(None, s, c).ratio())
print(SequenceMatcher(None, s_t, c_t).ratio())
print(SequenceMatcher(None, withoutJunk(s_t, "~"), withoutJunk(c_t, "~")).ratio())
print(fuzz.ratio(s_t, c_t))
print(fuzz.ratio(withoutJunk(s_t, "~"), withoutJunk(c_t, "~")))

# m = StringMatcher("~", s_t, c_t)

print(ratio(s, c))
print(ratio(s_t, c_t))
print(ratio(withoutJunk(s_t, "~"), withoutJunk(c_t, "~")))
