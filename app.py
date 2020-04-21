import logging
import os

from flask import Flask
from slack import WebClient
from slackeventsapi import SlackEventAdapter

from onboarding_tutorial import OnboardingTutorial

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

app = Flask(__name__)

slack_events_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], '/slack/events', app)
slack_web_client = WebClient(os.environ['SLACK_BOT_TOKEN'])

user_onboarding_tutorial = {}


def start_onboarding(user_id, channel):
    tutorial = OnboardingTutorial(channel)
    msg = tutorial.get_message_payload()

    response = slack_web_client.chat_postMessage(**msg)

    # we have just posted a message for a particular user to take some actions on so store the message for that user,
    # so when the user in future performs actions, we can update their message
    if response['ok']:
        tutorial.timestamp = response['ts']
        user_onboarding_tutorial[user_id] = tutorial


@slack_events_adapter.on('message')
def message(payload):
    event = payload.get('event', {})

    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    if text and text.lower() == 'start':
        start_onboarding(user_id, channel_id)


@slack_events_adapter.on('reaction_added')
def reaction_added(payload):
    event = payload.get('event', {})

    # if user added a reaction to their onboarding message, update the message
    user = event.get('user')
    if user not in user_onboarding_tutorial:
        return

    tutorial = user_onboarding_tutorial[user]

    # grab the item the user reacted to in slack and verify that it is the tutorial message
    item = event.get('item')

    if item['type'] == 'message':
        channel = item['channel']
        ts = item['ts']

        if tutorial.channel == channel and tutorial.timestamp == ts:
            tutorial.reaction_task_completed = True

            # update the tutorial message
            msg = tutorial.get_message_payload()
            response = slack_web_client.chat_update(**msg)

            if response['ok']:
                tutorial.timestamp = response['ts']

            # if the user has completed finished the tutorial, no need to keep this task around
            if tutorial.reaction_task_completed and tutorial.pin_task_completed:
                del user_onboarding_tutorial[user]
