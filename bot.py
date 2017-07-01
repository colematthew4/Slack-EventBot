# -*- coding: utf-8 -*-
"""Python Slack Bot class for use with the EventScheduler app"""

from security_fields import *
from slackclient import SlackClient
from flask import jsonify
import re
from datetime import datetime, date
import time
import pymssql


class Bot(object):
	""" Instantiates a Bot object to handle Slack onboarding interactions."""

	def __init__(self):
		super(Bot, self).__init__()
		self.oauth = {'client_id': CLIENT_ID,
		              'client_secret': CLIENT_SECRET,
		              'scope': 'bot,commands'}
		self.verification = VERIFICATION_TOKEN

		# Slack requires a client connection to generate an oauth token. We can connect to the client without
		# authenticating by passing an empty string as a token and then re-instantiating the client with a valid OAuth
		# token once we have one.
		self.client = SlackClient(OAUTH_TOKEN)
		self.messages = {}      # so we can easily keep track of event fields when we attempt to create an event

	def auth(self, code):
		"""
		Authenticate with OAuth and assign correct scopes.
        Save a dictionary of authenticated team information in memory on the bot
        object.
		:param code: str
			temporary authorization code sent by Slack to be exchanged for an OAuth token
		"""
		# After the user has authorized this app for use in their Slack team, Slack returns a temporary authorization
		# code that we'll exchange for an OAuth token using the oauth.access endpoint
		self.client.api_call('oauth.access',
		                     client_id = self.oauth['client_id'],
		                     client_secret = self.oauth['client_secret'],
		                     code = code)

		# get the users in the team we just joined and add them to the database
		users = self.client.api_call('users.list', token = self.client.token)

		# open up a database connection
		with pymssql.connect(server = DB_SERVER, user = DB_USER, password = DB_PASSWORD, database = DB_NAME) as db_conn:
			with db_conn.cursor(as_dict = True) as cursor:
				for user in users['members']:
					if not user['deleted']:     # we don't want to add deleted users
						cursor.callproc('CreateSlackUser', (user['id'], user['name']))
			db_conn.commit()    # if you don't commit the changes, the transaction will be rolled back

	def welcome(self, user):
		"""
		Create and send a welcome message to new users.
		:param user: dict
				The information on the user how just joined the team
		:return: The response json message from Slack after posting a message to a channel
		"""
		# open up a database connection
		with pymssql.connect(server = DB_SERVER, database = DB_NAME, user = DB_USER, password = DB_PASSWORD) as db_conn:
			with db_conn.cursor(as_dict = True) as cursor:
				cursor.callproc('CreateSlackUser', (user['id'], user['name']))
			db_conn.commit()    # if you don't commit the changes, the transaction will be rolled back

		# send a welcome message to the user who just joined
		response = self.client.api_call('chat.postMessage',
		                                token = self.client.token,
		                                channel = 'general',
		                                text = 'Welcome @%s!' % user['name'],
		                                as_user = False)

		if response['ok']:
			return 'Message Sent'
		else:
			return 'Message Failed'

	def show_help(self):
		"""
		Sends a message to Slack that explains how to use the /event slash command. This message can only be seen by the
		user who invoked the /event command.
		:return: A json message that displays to the Slack user how to use the /event slash command.
		"""
		return jsonify({
			'response_type': 'ephemeral',                       # by making this ephemeral, only the user can see it
			'text': 'Need some help with `/event`?\n'
			        'Use `/event help` to see this message again, or use it to view, join, or leave existing scheduled '
			        'events or schedule new ones! Here are some examples:\n'
			        'Just typing `/event` is the same as typing `/event help`\n'
			        '`/event all` will display all of your events one at a time\n'
			        '`/event new : Go to Lisa\'s wedding : 3:00 pm : 06/19/17` will create a new event and set a Slack '
			        'reminder for you at 3 pm on June 6, 2017',
			'content-type': 'application/json'
		})

	def show_new(self, text, user):
		"""
		Sends a message to Slack that gives a summary of the event that will be created based on the arguments given by
		the invoked /event command. This message will supply two message buttons as attachments so the Slack user who
		invoked the /event command can verify the information before the event and a Slack reminder is created. This
		message can only be seen by the user who invoked the /event command.
		:param text: str
				The description of the event, the time it occurs, and the date on which it occurs that the Slack user
				gave in the command arguments.
		:param user: str
				The id of the Slack user who invoked the command.
		:return: A json message that displays to the Slack user how the event will be stored, and contains interactive
				buttons for the user to confirm the event or cancel it.
		"""
		_date = datetime.today()
		result = re.search(r'(\d+/\d+/\d+)', text)  # search for the date the event occurs on

		if result:
			temp = datetime.strptime(result.group(0), '%m/%d/%y')
			_date = date(temp.year, temp.month, temp.day)

		_time = re.search('([0-1][0-9]:[0-5][0-9]) [a|p]m', text)  # search for the time the event occurs at
		if _time:
			_time = _time.group()   # make sure a time was found
		else:
			_time = '12:00 am'      # give it a default time otherwise

		description = text.split(':')[1]    # get the description for the event

		# add the event data to the messages dictionary as a dictionary using the user's ID as the key. We do this
		# because in the button response, Slack doesn't send this information back to us. This allows us to easily
		# reference the event data to actually create it
		self.messages.update({user: {'date': _date, 'time': _time, 'text': description}})

		# return a json message to confirm the event
		return jsonify({
			'response_type': 'ephemeral',               # by making this ephemeral, only the user can see it
			'text': 'Is this correct?',
			'content-type': 'application/json',
			'replace_original': True,
			'attachments': [{
				'fallback': 'Your formatting was incorrect. Type \'/event help\' to see how to properly use EventBot',
				'callback_id': 'submit_new_event',
				'color': 'good',
				'title': 'Description',
				'text': description,
				'fields': [
					{
						'title': 'Time',
						'value': _time,
						'short': True       # setting this to true makes the fields appear side by side
					},
					{
						'title': 'Date',
						'value': '%d/%d/%d' % (_date.month, _date.day, _date.year),
						'short': True       # setting this to true makes the fields appear side by side
					}
				],
				'actions': [        # add buttons that will enable users to confirm or cancel the event
					{
						'name': 'YesButton',
						'text': 'Yes',
						'type': 'button',
						'value': 'submit',      # this is so we can tell what happened when we handle the button click
						'style': 'primary'      # color indicating proper/improper responses
					},
					{
						'name': 'NoButton',
						'text': 'No',
						'type': 'button',
						'value': 'cancel',      # this is so we can tell what happened when we handle the button click
						'style': 'danger'       # color indicating proper/improper responses
					}
				]
			}]
		})

	def get_event(self, user, event_id = 0):
		"""
		Gets an event from the database, regardless of who is in it.
		:param user: str
				The ID of the Slack user to get events for
		:param event_id: int
				The ID of the last event pulled from the database. The default is zero, which will pull the first event
				in the database.
		:return: A json message containing the info of the next event in the database.
		"""
		# open up a database connection
		with pymssql.connect(server = DB_SERVER, user = DB_USER, password = DB_PASSWORD, database = DB_NAME) as db_conn:
			with db_conn.cursor(as_dict = True) as cursor:
				try:
					cursor.callproc('GetNextEvent', (event_id,))    # get the next event from the database
					cursor.nextset()
					event = cursor.fetchall()

					# get the people participating in the event
					cursor.callproc('GetUsersInEvent', (event[0]['EventID'],))
					cursor.nextset()
					names = cursor.fetchall()

					if event and names:     # make sure there are events and people
						period = 'am'
						hour = re.search('^\d\d:', event[0]['EventTime']).group(0).replace(':', '')
						if int(hour) >= 12:
							hour = int(hour) - 12
							period = 'pm'
						minute = re.search(':\d\d:', event[0]['EventTime']).group(0).replace(':', '')

						names_in_event = ''
						for name in names:      # put all the names participating in the event into a single string
							names_in_event += name['Name'] + '\n'

						# is the current user already participating in the event? If so, give the json message a "Leave"
						# option, otherwise give it a "Join" option
						if any(name['SlackUserID'] == user for name in names):
							return jsonify({
								'response_type': 'ephemeral',       # by making this ephemeral, only the user can see it
								'content-type': 'application/json',
								'replace_original': True,
								'attachments': [{
									'fallback': 'You have no events scheduled',
									'callback_id': 'get_event',
									'title': 'Event',
									'text': event[0]['EventDescription'],
									'fields': [
										{
											'title': 'Time',
											'value': '%s:%s %s' % (hour, minute, period),
											'short': True    # setting this to true makes the fields appear side by side
										},
										{
											'title': 'Date',
											'value': event[0]['EventDate'],
											'short': True    # setting this to true makes the fields appear side by side
										},
										{
											'title': 'Attendees',
											'value': names_in_event,
											'short': True    # setting this to true makes the fields appear side by side
										}
									],
									'actions': [
										# we are passing the event ID as the value on these buttons that way when the
										# user clicks one of these buttons, we know what the next event in the database
										# to get is
										{
											'name': 'LeaveEventButton',
											'text': 'Leave',
											'type': 'button',
											'value': event[0]['EventID'],
										},
										{
											'name': 'NextEventButton',
											'text': 'Next',
											'type': 'button',
											'value': event[0]['EventID'],
											'style': 'primary'      # color indicating proper/improper responses
										}
									]
								}]
							})
						else:
							return jsonify({
								'response_type': 'ephemeral',       # by making this ephemeral, only the user can see it
								'content-type': 'application/json',
								'replace_original': True,
								'attachments': [{
									'fallback': 'You have no events scheduled',
									'callback_id': 'get_event',
									'title': 'Event',
									'text': event[0]['EventDescription'],
									'fields': [
										{
											'title': 'Time',
											'value': '%s:%s %s' % (hour, minute, period),
											'short': True    # setting this to true makes the fields appear side by side
										},
										{
											'title': 'Date',
											'value': event[0]['EventDate'],
											'short': True    # setting this to true makes the fields appear side by side
										},
										{
											'title': 'Attendees',
											'value': names_in_event,
											'short': True    # setting this to true makes the fields appear side by side
										}
									],
									'actions': [
										# we are passing the event ID as the value on these buttons that way when the
										# user clicks one of these buttons, we know what the next event in the database
										# to get is
										{
											'name': 'JoinEventButton',
											'text': 'Join',
											'type': 'button',
											'value': event[0]['EventID'],
										},
										{
											'name': 'NextEventButton',
											'text': 'Next',
											'type': 'button',
											'value': event[0]['EventID'],
											'style': 'primary'      # color indicating proper/improper responses
										}
									]
								}]
							})
					else:
						raise pymssql.DatabaseError('No events')
				except pymssql.DatabaseError as e:
					print e.message
					return jsonify({
						'response_type': 'ephemeral',       # by making this ephemeral, only the user can see it
						'text': 'You have no more scheduled events',
						'content-type': 'application/json',
						'replace-original': True            # this message will replace the original
					})

	def get_my_event(self, user, event_id = 0):
		"""
		Gets an event from the database.
		:param user: str
				The ID of the Slack user to get events for.
		:param event_id: int
				The ID of the last event pulled from the database. The default is zero, which will pull the first event
				in the database.
		:return: A json message containing the info of the next event in the database.
		"""
		# open up a database connection
		with pymssql.connect(server = DB_SERVER, user = DB_USER, password = DB_PASSWORD, database = DB_NAME) as db_conn:
			with db_conn.cursor(as_dict = True) as cursor:
				try:
					cursor.callproc('GetUserEvent', (user, event_id))
					cursor.nextset()
					event = cursor.fetchall()
					cursor.callproc('GetUsersInEvent', (event[0]['EventID'],))
					cursor.nextset()
					names = cursor.fetchall()

					if event and names:
						period = 'am'
						hour = re.search('^\d\d:', event[0]['EventTime']).group(0).replace(':', '')
						if int(hour) >= 12:
							hour = int(hour) - 12
							period = 'pm'
						minute = re.search(':\d\d:', event[0]['EventTime']).group(0).replace(':', '')

						names_in_event = ''
						for name in names:
							names_in_event += name['Name'] + '\n'

						return jsonify({
							'response_type': 'ephemeral',       # by making this ephemeral, only the user can see it
							'content-type': 'application/json',
							'replace_original': True,
							'attachments': [{
								'fallback': 'You have no events scheduled',
								'callback_id': 'get_my_event',
								'title': 'Event',
								'text': event[0]['EventDescription'],
								'fields': [
									{
										'title': 'Time',
										'value': '%s:%s %s' % (hour, minute, period),
										'short': True    # setting this to true makes the fields appear side by side
									},
									{
										'title': 'Date',
										'value': event[0]['EventDate'],
										'short': True    # setting this to true makes the fields appear side by side
									},
									{
										'title': 'Attendees',
										'value': names_in_event,
										'short': True    # setting this to true makes the fields appear side by side
									}
								],
								'actions': [
									# we are passing the event ID as the value on these buttons that way when the
									# user clicks one of these buttons, we know what the next event in the database
									# to get is
									{
										'name': 'LeaveEventButton',
										'text': 'Leave',
										'type': 'button',
										'value': event[0]['EventID'],
									},
									{
										'name': 'NextEventButton',
										'text': 'Next',
										'type': 'button',
										'value': event[0]['EventID'],
										'style': 'primary'
									}
								]
							}]
						})
					else:
						raise pymssql.DatabaseError('No events')
				except pymssql.DatabaseError as e:
					print e.message
					return jsonify({
						'response_type': 'ephemeral',       # by making this ephemeral, only the user can see it
						'text': 'You have no more scheduled events',
						'content-type': 'application/json',
						'replace-original': True            # this message will replace the original
					})

	def create_event(self, description, _date, _time, user):
		"""
		Creates an event in the database and adds a reminder for the user.
		:param description: str
				The description given for the event.
		:param _date: str
				The date when the event occurs.
		:param _time: str
				The time when the event occurs.
		:param user: str
				The ID of the Slack user who is creating the event.
		:return: The json response that Slack returns when creating a reminder, or an error message.
		"""
		# open up a database connection
		with pymssql.connect(server = DB_SERVER, user = DB_USER, password = DB_PASSWORD, database = DB_NAME) as db_conn:
			with db_conn.cursor(as_dict = True) as cursor:
				try:
					period = re.search('[a|p]m', _time).group()
					hour = re.match('[0-1][0-9]', _time).group()
					if period == 'pm':
						hour = str(int(hour) + 12)
					minute = re.search(':[0-5][0-9]', _time).group().replace(':', '')

					# Get the unix epoch timestamp based on the date and time given.
					# This is required by Slack to create events
					timestamp = int(time.mktime(time.strptime('%d-%d-%d %d-%d-00' % (_date.year,
					                                                                 _date.month,
					                                                                 _date.day,
					                                                                 int(hour),
					                                                                 int(minute)),
					                                          '%Y-%m-%d %H-%M-%S')))

					cursor.callproc('CreateEvent', (user, description,
					                                '%d-%d-%d' % (_date.year, _date.month, _date.day),
					                                '%s:%s:00' % (hour, minute)))
					db_conn.commit()    # if you don't commit the changes, the transaction will be rolled back

					response = self.client.api_call('reminders.add',
					                                token = self.client.token,
					                                text = description,
					                                time = timestamp,
					                                user = user)

					if response['ok']:
						return 'Reminder successfully created'
					else:
						return 'Failed to create reminder'
				except pymssql.DatabaseError as e:
					print e.message
					return jsonify({
						'response_type': 'ephemeral',       # by making this ephemeral, only the user can see it
						'text': 'An error occurred trying to create the event.',
						'content-type': 'application/json',
						'replace-original': True            # this message will replace the original
					})

	def join_event(self, user, event_id):
		"""
		Adds a user to an event and creates a Slack reminder.
		:param user: str
				The ID of the Slack user to add to the event.
		:param event_id: int
				The ID of the event to add the Slack user to.
		:return: The json response that Slack returns when creating a reminder, or an error message.
		"""
		# open up a database connection
		with pymssql.connect(server = DB_SERVER, user = DB_USER, password = DB_PASSWORD, database = DB_NAME) as db_conn:
			with db_conn.cursor(as_dict = True) as cursor:
				try:
					cursor.callproc('AddUserToEvent', (user, event_id))
					db_conn.commit()        # if you don't commit the changes, the transaction will be rolled back

					cursor.execute('select EventDescription, EventDate, EventTime '
					               'from [Event] join SlackUserToEvent on [Event].EventID = SlackUserToEvent.EventID '
					               'where SlackUserID = %s and [Event].EventID = %s', (user, event_id))
					event = cursor.fetchall()

					if event:
						# Get the unix epoch timestamp based on the date and time given.
						# This is required by Slack to create reminders
						timestamp = int(time.mktime(time.strptime('%s %s' % (event[0]['EventDate'],
						                                                     event[0]['EventTime']),
						                                          '%Y-%m-%d %H:%M:%S.0000000')))

						response = self.client.api_call('reminders.add',
						                                token = self.client.token,
						                                text = event[0]['EventDescription'],
						                                time = timestamp,
						                                user = user)

						if response['ok']:
							return 'Reminder successfully created'
						else:
							return 'Failed to create reminder'
					else:
						raise pymssql.DatabaseError('Failed to join event')
				except pymssql.DatabaseError as e:
					print e.message
					return jsonify({
						'response_type': 'ephemeral',       # by making this ephemeral, only the user can see it
						'text': 'You could not be added to the event',
						'content-type': 'application/json',
						'replace-original': True            # this message will replace the original
					})

	def leave_event(self, user, event_id):
		"""
		Removes a user from an event and creates a Slack reminder.
		:param user: str
				The ID of the Slack user to add to the event.
		:param event_id: int
				The ID of the event to add the Slack user to.
		:return: The json response that Slack returns when creating a reminder, or an error message.
		"""
		# open up a database connection
		with pymssql.connect(server = DB_SERVER, user = DB_USER, password = DB_PASSWORD, database = DB_NAME) as db_conn:
			with db_conn.cursor(as_dict = True) as cursor:
				try:
					cursor.execute('select EventDescription, EventDate, EventTime '
					               'from [Event] join SlackUserToEvent on [Event].EventID = SlackUserToEvent.EventID '
					               'where SlackUserID = %s and [Event].EventID = %s', (user, event_id))
					event = cursor.fetchall()

					cursor.callproc('LeaveEvent', (user, event_id))
					db_conn.commit()        # if you don't commit the changes, the transaction will be rolled back

					if event:
						reminders = self.client.api_call('reminders.list', token = self.client.token)

						# Get the unix epoch timestamp based on the date and time given.
						# This is required by Slack to create reminders
						timestamp = int(time.mktime(time.strptime('%s %s' % (event[0]['EventDate'],
						                                                     event[0]['EventTime']),
						                                          '%Y-%m-%d %H:%M:%S.0000000')))
						message = 'No reminders to delete'
						if any(reminders['reminders']):
							_id = next((reminder for reminder in reminders['reminders']
							            if reminder['text'] == event[0]['EventDescription'] and reminder['time'] == timestamp),
							           None)
							if _id:
								response = self.client.api_call('reminders.delete',
								                                token = self.client.token,
								                                reminder = _id['id'])

								if response['ok']:
									message = 'Reminder successfully deleted'
								else:
									message = 'Failed to delete reminder'
							else:
								message = 'No reminders to delete'

						return message
					else:
						raise pymssql.DatabaseError('You could not be added to the event')
				except pymssql.DatabaseError as e:
					return jsonify({
						'response_type': 'ephemeral',       # by making this ephemeral, only the user can see it
						'text': e.message,
						'content-type': 'application/json',
						'replace-original': True            # this message will replace the original
					})
