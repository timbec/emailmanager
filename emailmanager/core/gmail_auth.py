import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

CREDS_PATH = "credentials.json"
TOKEN_PATH = "token.json"


def authenticate_gmail():
    """
    OAuth flow using run_local_server() safely.
    - open_browser=False avoids Edge opening automatically
    - port=0 binds any free port (no Errno 48)
    - URL prints to console so you can open it manually in Chrome
    """

    creds = None

    # Reuse existing token if present
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # Otherwise start a new OAuth flow
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)

        # Important: open_browser=False prevents Edge from launching
        creds = flow.run_local_server(open_browser=False, port=0)

        print("\nOAuth URL (copy/paste into Chrome):")
        print(flow.redirect_uri)
        print("\n")

        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
