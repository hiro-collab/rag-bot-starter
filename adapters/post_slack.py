import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Minimal Slack poster (no interactivity yet)
def post_message(channel: str, text: str):
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN not set")
    client = WebClient(token=token)
    try:
        client.chat_postMessage(channel=channel, text=text)
    except SlackApiError as e:
        raise RuntimeError(f"Slack error: {e.response['error']}")
