# AutoCorrect Marker Bot for Reddit
This bot helps the moderators of the WriteStreak subreddits by automatically classifying the 
submissions as corrected or not. The bot simply compares every comment in a submission and if it is similar marks 
the submission as corrected.  
For submissions that the bot cannot categorize it either reports it to the moderator team or simply ignores them for 
the time being.  
The bot will check every hour for every submission that has been done in the last week and is not yet marked as 
corrected.

## Configuration
YAML is used to configure the bot. Each subreddit that the bot manages is a top level entry of a YAML dictionary. 
Each subreddit allows for the following fields:
- **to_be_corrected_flair_id** - if present, only process the submissions with this flair, 
  otherwise process all submissions
- **corrected_flair_id - if present marks the submissions as corrected otherwise not
- **bot_comment - if present the bot leaves a comment with this message
- mod_team_message - if present the bot send a message to the moderators on the posts that the bot is not able to 
  decide
- similarity_correction_threshold - overrides the default value for the correction threshold in this subreddit
- similarity_investigate_threshold - overrides the default value for the investigation threshold in this subreddit

### Example:
```yaml
"test_subreddit":
    "to_be_corrected_flair_id": "2360392c-bd3f-11eb-9619-0e91ce9de8e5"
    "corrected_flair_id": "25e9e6de-bd3f-11eb-81a6-0edbdca81731"
    "bot_comment": "Esta submissão foi automaticamente classificada com corrigida por um bot. Se discordar, por
    favor contacte os moderadores
    .\n\n**------------------------------------------------------------------------------------------------------**\n
    \nThis submission was automatically classified as corrected by a bot. If you disagree, please reach out to the
    mod team.\n\n**AutoCorrectBot**"
    "mod_team_message": "Hi, I am not sure but I think [comment](COMMENT_LINK) might be a correction for [this]
    (SUBMISSION_LINK) submission. I need the help of an human.\n\nBlip blop.\n\n**AutoCorrectBot**"
    "similarity_correction_threshold": 0.15 # from 0 to 1, above marks post as corrected, default is 0.15
    "similarity_investigate_threshold": 0.04 # from 0 to 1, above marks post as to be investigated, default is 0.04
```