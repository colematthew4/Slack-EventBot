# Slack-EventBot
Create or leave events, and view the Slack users attending an event
***********************************************************************************************************************************************************
Published by:	 Matthew Cole
CST 223 - Concepts of Programming Langauges
Spring 2017
***********************************************************************************************************************************************************

Welcome to the setup for the Slack EventScheduler application.

Let me begin by stating that setup for this project is fairly long and complex. When you open the .zip or .tar file, you will find a Templates folder and a
couple files:

app.py
bot.py
DB script.sql
security_fields.py
ngrok.exe

The DB script.sql file is strictly for setting up the database to store the information. It should not be necessary to run this, as there is a database
already setup for this project. Within the Templates folder is 2 .html files, which are used for installing the bot to other teams. This is also
unnecessary for this demo. Before we can run the application, we need to make sure we have all the required Python libraries and update the request URLs 
that Slack will send events to so our application can communicate with Slack. This is where the ngrok.exe comes into play.

Before we start using ngrok, you will need to install the python-slackclient, flask, and pymssql Python packages. This can be done using pip or
easy_install (easy_install is the old version for installing Python packages). In order to do this, type

pip install <package-name>
	or
sudo easy_install <package-name>

in the Python console. You may need to authenticate yourself as a "sudoer" in order to use easy_install. Now try to run the application, and you should see
something like this:

 * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
 * Restarting with stat
 * Debugger is active!
 * Debugger PIN: 223-166-435

This means that the application is running correctly and listening for incoming JSON requests.

Ngrok is an application that takes your localhost IP address and converts it into a unique HTTP/HTTPS URL. Slack requires an appliction's request URLs to
be SSL certified, that's why we can't just use our localhost IP address. While the application is running, open execute ngrok.exe and type:

ngrok.exe http 5000

This will open the communication channel and display the HTTP URLs that we need for Slack to communicate with our application. We will specifically need
the HTTPS URL. Now we need to log in to Slack and add an integration to your team.



***********************************************************************************************************************************************************
Go to your browser and navigate to slack.com and click on the "Sign In" button in the top right. From here Slack should redirect you to the team itself, 
where you can go to https://api.slack.com/apps to create the integration and apply the necessary application settings. This is where we need the HTTPS URL 
from ngrok. In the EventScheduler application settings page, go to the Interactive Messages tab, copy the ngrok URL, and paste it into the request URL with
the /button endpoint. Your new request URL should look something like this: 

https://4f72b87c.ngrok.io/button

Click "Save Changes" and go to the Slash Commands tab and click the edit button the /event command. Do the same thing as you did for the Interactive 
Messages request URL, but use the /event endpoint instead of the /button endpoint, and click "Save". The request URL for the slash command should look 
something like this:

https://4f72b87c.ngrok.io/event

Now go to the OAuth & Permissions tab, and again do the same for the redirect URL. We won't actually be using this, but it's better for it to be the same
for consistency's sake. The endpoint for the OAuth & Permissions should be /thanks, so your redirect URL should look like this:

https://4f72b87c.ngrok.io/thanks

Now go to the Event Subscriptions tab. Make sure you click "Save", and then click "Save URLS" right underneath. This is the last URL we need to change
with the application. However, make sure the application itself is still running, because when we change this request URL Slack will send a "challenge"
message to the application for it to verify. Make sure the endpoint for the Event Subscriptions Request URL is /listening. If successful, it must look 
something like this:

https://4f72b87c.ngrok.io/listening

After you click "Save Changes", the EventScheduler application should be fully up and running, and you can create and view events. Make sure to type 
"/event help" before you use it so you understand how it works.



***********************************************************************************************************************************************************
Thanks for using the Slack EventScheduler application. If you have questions or issues, email support at matthew.cole@oit.edu and I will attempt to help
you as best I can.
