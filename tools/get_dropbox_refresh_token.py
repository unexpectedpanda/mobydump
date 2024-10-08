import base64
import json
import os
import requests

from dotenv import load_dotenv

# Get the contents of the .env file
load_dotenv()

# Initial setup:
#
# 1.  Go to https://www.dropbox.com/developers/apps, create a new app, and get your
#     Dropbox app key and secret
# 2.  Assign them to DROPBOX_APP_KEY and DROPBOX_APP_SECRET in the same .env file you
#     stored MOBY_API in.
# 3.  Visit the following URL, replacing the <DROPBOX_APP_KEY> value:
#
#     https://www.dropbox.com/oauth2/authorize?client_id=<DROPBOX_APP_KEY>&response_type=code&token_access_type=offline
#
# 4.  Assign the access code you're given to DROPBOX_ACCESS_CODE in the .env file.
#
# 5.  Run this script to get your refresh token, which you need to be able to request
#     short-lived tokens on an ongoing basis.
#
#     You can only use an access code once. If you mess up, you'll need to get another one
#     and run the script again.
#
# 6.  From the response to this script, assign the refresh_key value to
#     DROPBOX_REFRESH_TOKEN in the .env file.

# Get a refresh token
if os.getenv('DROPBOX_ACCESS_CODE') and os.getenv('DROPBOX_APP_KEY') and os.getenv('DROPBOX_APP_SECRET'):
    dropbox_access_code = str(os.getenv('DROPBOX_ACCESS_CODE'))
    dropbox_app_key = str(os.getenv('DROPBOX_APP_KEY'))
    dropbox_app_secret = str(os.getenv('DROPBOX_APP_SECRET'))

    basic_auth = base64.b64encode(f'{dropbox_app_key}:{dropbox_app_secret}'.encode())

    headers = {
        'Authorization': f"Basic {basic_auth}",
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    data = f'code={dropbox_access_code}&grant_type=authorization_code'

    response = requests.post('https://api.dropboxapi.com/oauth2/token',
                            data=data,
                            auth=(dropbox_app_key, dropbox_app_secret))

    print(json.dumps(json.loads(response.text), indent=2))
else:
    print(f'You need a Dropbox access code, app key, and app secret defined in .env to continue')