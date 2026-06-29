import os
import datetime
import requests
from google_auth_oauthlib.flow import InstalledAppFlow

# Force the OAuth library to accept scope differences cleanly
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Only the new Google Health scope
SCOPES = [
    'https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly',
    'https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly'
]
CLIENT_SECRET_FILE = '/app/client_secret_461691553363-o8tldjjnhkto4thldq785f13tiir90jg.apps.googleusercontent.com.json'

def main():
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    flow.redirect_uri = 'http://127.0.0.1'

    auth_url, _ = flow.authorization_url(prompt='consent', include_granted_scopes='false')
    
    print("\n====================================================")
    print("1. OPEN THIS URL IN YOUR PHONE/BROWSER TO AUTHORIZE:")
    print("====================================================")
    print(auth_url)
    print("====================================================\n")
    
    url_input = input("2. PASTE THE FULL 127.0.0.1 URL HERE AND PRESS ENTER:\n").strip()
    
    if "code=" in url_input:
        code = url_input.split("code=")[1].split("&")[0]
    else:
        code = url_input

    print("\nExchanging code for access token...")
    flow.fetch_token(code=code)
    credentials = flow.credentials
    print("SUCCESS ✔ Token acquired.")

    # -----------------------------------------------------------------
    # FIX: Save the credentials safely to a permanent file on disk!
    # -----------------------------------------------------------------
    with open('token.json', 'w') as token_file:
        token_file.write(credentials.to_json())
    print("💾 Session saved permanently to token.json!")

if __name__ == '__main__':
    main()