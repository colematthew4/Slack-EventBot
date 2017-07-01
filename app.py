# -*- coding: utf-8 -*-
"""
A routing layer for the onboarding bot tutorial built using
[Slack's Events API](https://api.slack.com/events-api) in Python
"""
import json
import bot
from flask import Flask, request, make_response, render_template
import re

app = Flask(__name__)   # create a Flask application to receive and send json messages
eventBot = bot.Bot()    # instantiate a bot to handle incoming requests


def _event_handler(event_type, slack_event):
    """
    A helper function that routes events from Slack to our Bot by event type and subtype.
    :param event_type: str
        type of event received from Slack
    :param slack_event: dict
        JSON response from a Slack reaction event
    :return: Response object with 200 - ok or 404 - No Event Handler error
    """
    # When a user first joins a team, the type of event will be team_join
    if event_type == 'team_join':
        eventBot.welcome(slack_event['user'])        # Send the welcoming message
        return make_response('Welcome Message Sent', 200,)

    # When a user has invoked the /event slash command and wants to know how to use it
    elif event_type == 'help':
        message = eventBot.show_help()
        return make_response(message, 200,)

    # When a user has invoked the /event slash command and wants to create a new event
    elif event_type == 'new':
        text = slack_event['text']
        # remove the 'new' command argument from the text and pass it to the bot
        message = eventBot.show_new(text.replace('new', ''), slack_event['user_id'])
        return make_response(message, 200,)

    # When a user has invoked the /event slash command and wants to see all scheduled events
    elif event_type == 'all':
        message = eventBot.get_event(slack_event['user_id'])
        return make_response(message, 200,)

    # When a user has invoked the /event slash command and wants to see the events they are in
    elif event_type == 'me':
        message = eventBot.get_my_event(slack_event['user_id'])
        return make_response(message, 200,)

    # If the event_type does not have a handler, return a helpful error message
    message = 'You have not added an event handler for the %s' % event_type
    return make_response(message, 404, {'X-Slack-No-Retry': 1})


@app.route('/install', methods=['GET'])
def pre_install():
    """
    ============ Render Slack Install Button ===========
    This route renders the installation page with an 'Add to Slack' button.
    """
    # Since we've set the client ID and scope on our Bot object, we can change them more easily while we're developing
    # our app.
    client_id = eventBot.oauth['client_id']
    scope = eventBot.oauth['scope']
    # Our template is using the Jinja templating language to dynamically pass our client id and scope
    return render_template('install.html', client_id=client_id, scope=scope)


@app.route('/thanks', methods=['GET', 'POST'])
def thanks():
    """
    ============ Slack App Installed ===========
    This route is called by Slack after the user installs our app. It will exchange the temporary authorization code
    Slack sends for an OAuth token which we'll save on the bot object to use later. To let the user know what's happened
    it will also render a thank you page.
    """
    # Let's grab that temporary authorization code Slack's sent us from the request's parameters.
    code_arg = request.args['code']
    # The bot's auth method to handle exchanging the code for an OAuth token
    eventBot.auth(code_arg)
    return render_template('thanks.html')


@app.route('/listening', methods=['GET', 'POST'])
def listen():
    """
    ============ Slack Chat Event Invocation ===========
    This route listens for incoming events from Slack and uses the event handler helper function to route events to
    EventBot.
    :return: Response object with 200 - ok or 404 - No Event Handler error
    """
    slack_event = json.loads(request.data)

    # ============= Slack URL Verification ============ #
    # In order to verify the url of our endpoint, Slack will send a challenge token in a request and check for this
    # token in the response our endpoint sends back. For more info: https://api.slack.com/events/url_verification
    if 'challenge' in slack_event:
        return make_response(slack_event['challenge'], 200, {'content_type': 'application/json'})

    # Verify that the request came from Slack
    if not check_token(slack_event):
        # If the incoming request is an event we've subscribed to
        if 'event' in slack_event:
            event_type = slack_event['event']['type']
            # Then handle the event by event_type and have your bot respond
            return _event_handler(event_type, slack_event)

    # If our bot hears things that are not events we've subscribed to, send a quirky but helpful error response
    return make_response('[NO EVENT IN SLACK REQUEST] These are not the droids you\'re looking for.', 404,
                         {'X-Slack-No-Retry': 1})


@app.route('/event', methods=['POST'])
def slash_event():
    """
    ============ Slack Slash Event Invocation ===========
    This route listens for invocations of the /event slash command and uses the event handler helper function to route
    events to EventBot.
    :return: Response object with 200 - ok or 404 - No Event Handler error
    """
    slack_event = request.values

    # Verify that the request came from Slack
    if not check_token(slack_event):
        # if text starts with 'help', send message for more information on how to use command
        if re.match('help', slack_event['text']):
            event_type = 'help'
            return _event_handler(event_type, slack_event)
        elif re.match('all', slack_event['text']):
            event_type = 'all'
            return _event_handler(event_type, slack_event)
        elif re.match('me', slack_event['text']):
            event_type = 'me'
            return _event_handler(event_type, slack_event)
        elif re.match('new', slack_event['text']):
            event_type = 'new'
            return _event_handler(event_type, slack_event)

        # If we hear things that are not events we've subscribed to, send a quirky but helpful error response
        return make_response('[NO EVENT IN SLACK REQUEST] These are not the droids you\'re looking for.', 404,
                             {'X-Slack-No-Retry': 1})


@app.route('/button', methods=['POST'])
def button_event():
    """
    ============ Slack Message Button Invocation ===========
    This route listens for incoming message button actions.
    :return: Response object with 200 - ok or 404 - No Event Handler error
    """
    slack_event = json.loads(request.values['payload'])

    # Verify that the request came from Slack
    response = check_token(slack_event)
    if not response:
        try:
            if slack_event['callback_id'] == 'submit_new_event' and slack_event['actions'][0]['value'] == 'submit':
                user = slack_event['user']['id']                    # the ID of the Slack user
                _date = eventBot.messages[user]['date']             # the date of the event
                _time = eventBot.messages[user]['time']             # the time of the event
                _text = eventBot.messages[user]['text']             # the description of the event
                response = eventBot.create_event(_text, _date, _time, user)     # create the event
                del eventBot.messages[user]                         # delete the temporary event data storage
            elif slack_event['callback_id'] == 'submit_new_event' and slack_event['actions'][0]['value'] == 'cancel':
                del eventBot.messages[slack_event['user']['id']]    # delete the temporary event data storage
                response = eventBot.show_help()            # display a help message so they can properly use the command
            elif slack_event['callback_id'] == 'get_my_event' and slack_event['actions'][0]['name'] == 'NextEventButton':
                user = slack_event['user']['id']                    # the ID of the Slack user
                event_id = slack_event['actions'][0]['value']       # the ID of the event being displayed
                response = eventBot.get_my_event(user, event_id)    # get the next event
            elif slack_event['callback_id'] == 'get_event' and slack_event['actions'][0]['name'] == 'NextEventButton':
                user = slack_event['user']['id']                    # the ID of the Slack user
                event_id = slack_event['actions'][0]['value']       # the ID of the event being displayed
                response = eventBot.get_event(user, event_id)       # get the next event
            elif slack_event['callback_id'] in ('get_event', 'get_my_event') and slack_event['actions'][0]['name'] == 'LeaveEventButton':
                user = slack_event['user']['id']                    # the ID of the Slack user
                event_id = slack_event['actions'][0]['value']       # the ID of the event being displayed
                eventBot.leave_event(user, event_id)                # leave the event
                response = eventBot.get_event(user, event_id)       # get the next event
            elif slack_event['callback_id'] == 'get_event' and slack_event['actions'][0]['name'] == 'JoinEventButton':
                user = slack_event['user']['id']                    # the ID of the Slack user
                event_id = slack_event['actions'][0]['value']       # the ID of the event being displayed
                eventBot.join_event(user, event_id)                 # join the event
                response = eventBot.get_event(user, event_id)       # get the next event

            return make_response(response, 200,)        # send a response back
        except (KeyError, ValueError) as e:
            print e.message
            response = 'Failed to create event'

    # If our bot hears things that are not events we've subscribed to, send a helpful error response
    return make_response(response, 404, {'X-Slack-No-Retry': 1})


def check_token(slack_event):
    """
    ============ Slack Token Verification ===========
    We can verify the request is coming from Slack by checking that the verification token in the request matches our
    app's settings.
    :param slack_event: dict
            JSON response from a Slack reaction event
    :return: Responds with None if verification is successful, or a json object with 404 - No Event Handler error
    """
    if slack_event['token'] != eventBot.verification:
        return 'Invalid Slack verification token: %s \neventBot has: %s\n\n' % (slack_event['token'], eventBot.verification)

    return None

if __name__ == '__main__':
    app.run(debug=True)
