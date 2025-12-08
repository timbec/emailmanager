from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from django.http import JsonResponse


# ------------------------------------------------------------
# Test Authentication (mirrors FastAPI behavior exactly)
# ------------------------------------------------------------
def test_authentication():
    """
    Attempts to authenticate to Gmail and fetch the user's profile.
    Returns True/False exactly like your FastAPI version.
    """
    from .gmail_auth import authenticate_gmail   # avoid circular import

    try:
        service = authenticate_gmail()
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress")
        print(f"Authentication successful! Email address: {email_address}")
        return True

    except Exception as e:
        print(f"Authentication failed: {e}")
        return False


# ------------------------------------------------------------
# List recent unread emails (ported from FastAPI)
# ------------------------------------------------------------
def list_recent_unread_emails(service, days=30):
    """
    Returns a list of unread emails newer than `days`.
    Mirrors the FastAPI version exactly, including header extraction.
    """
    date_cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
    query = f"is:unread after:{date_cutoff}"

    try:
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=50  # identical to your FastAPI code
        ).execute()

        messages = results.get("messages", [])
        email_list = []

        if not messages:
            print("No unread emails found for the specified period.")
            return email_list

        # Loop through and extract headers
        for message in messages:
            msg = service.users().messages().get(
                userId="me",
                id=message["id"]
            ).execute()

            headers = msg["payload"]["headers"]

            subject = next(
                (h["value"] for h in headers if h["name"] == "Subject"),
                "No Subject"
            )
            from_email = next(
                (h["value"] for h in headers if h["name"] == "From"),
                "Unknown Sender"
            )

            # 1. Try to get the email date from the "Date:" header
            date_str = next(
                (h["value"] for h in headers if h["name"] == "Date"),
                None
            )

            # 2. Fallback to Gmail's internalDate (epoch ms)
            if date_str:
                try:
                    parsed_date = datetime.strptime(
                        date_str[:25], "%a, %d %b %Y %H:%M:%S"
                    )
                except Exception:
                    # Some Date headers include timezone or nonstandard format
                    parsed_date = date_str
            else:
                internal_ms = int(msg.get("internalDate", 0))
                parsed_date = datetime.fromtimestamp(internal_ms / 1000)

            email_list.append({
                "from": from_email,
                "subject": subject,
                "date": parsed_date if isinstance(parsed_date, str) else parsed_date.isoformat()
            })

        print(f"From: {from_email}, Subject: {subject}")

        return email_list

    except Exception as e:
        print(f"Error occurred while listing emails: {e}")
        return []
    


def list_oldest_unread_emails(service, limit, days):
    """
    Returns the oldest unread emails.
    
    Args:
        years_back (int): key optimization. Adds "older_than:Xy" to the query
                          so we don't waste time scanning new emails.
    """
    try:
        # --- Step 1: Construct a smart query ---
        # Instead of just "is:unread", we ask for "is:unread older_than:10y"
        # This jumps straight to the bottom of the stack.

        # Five years ago: 
        five_years_ago = (datetime.now() - timedelta(days=1825)).strftime('%Y/%m/%d')
        print('Five years ago: ', five_years_ago)
        query = f"is:unread before:{five_years_ago}"

        # Ten years ago: 
        ten_years_ago = (datetime.now() - timedelta(days=3650)).strftime('%Y/%m/%d')
        print('Ten years ago: ', ten_years_ago)
        query = f"is:unread before:{ten_years_ago}"

        years_ago = (datetime.now() - timedelta(days)).strftime('%Y/%m/%d')
        print('How many years ago: ', years_ago)
        query = f"is:unread before:{years_ago}"

        
        print(f"Searching with query: {query}") 

        messages_metadata = []
        next_page = None
        
        # We still cap this loop to prevent infinite hangs, but now 
        # we are looping through the RELEVANT (old) emails.
        safety_limit = 1000 
        
        while len(messages_metadata) < safety_limit:
            response = service.users().messages().list(
                userId="me",
                q=query, 
                pageToken=next_page,
                maxResults=500,
                fields="nextPageToken,messages(id, internalDate)"
            ).execute()

            msgs = response.get("messages", [])
            messages_metadata.extend(msgs)
            

            next_page = response.get("nextPageToken")
            
            # If we run out of pages, stop.
            if not next_page:
                break
        
        # If the query was too aggressive (e.g., no emails > 10 years old),
        # we might return an empty list. You could add logic here to fallback
        # to "older_than:5y" if len(messages_metadata) == 0.
        if not messages_metadata:
            print("No emails found that far back.")
            return []

        # --- Step 2: Sort what we found ---
        # Sort by internalDate (Ascending = Oldest first)
        # Sorting by internalDate ensures accuracy regardless of API order.
        
        # FIX: Use .get() with a fallback of '0' (for sorting) to prevent KeyError.
        # We also filter out any message that doesn't have an ID (optional, but clean).
        valid_messages = [msg for msg in messages_metadata if msg.get('id')]
        
        valid_messages.sort(
            key=lambda x: int(x.get('internalDate', 0))
        )
        
        # Now take the oldest 'limit' from the valid messages
        oldest_ids = valid_messages[:limit]

        # --- Step 3: Fetch Details ---
        detailed = []
        for msg_meta in oldest_ids:
            full = service.users().messages().get(
                userId="me",
                id=msg_meta["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()

            headers = full["payload"]["headers"]

            def get_header(name):
                return next(
                    (h["value"] for h in headers if h["name"] == name), 
                    "Unknown"
                )

            internal_ms = int(full.get("internalDate", 0))
            internal_dt = datetime.fromtimestamp(internal_ms / 1000)
            date_human = internal_dt.strftime("%a, %d %b %Y %I:%M %p")

            detailed.append({
                "id": full["id"],
                "subject": get_header("Subject"),
                "from": get_header("From"),
                "date_human": date_human,
                "snippet": full.get("snippet", "") # Added snippet for context
            })

        # return detailed
        return {
            "emails": detailed,
            "count": len(detailed) # Optional: Adds helpful context
        }

    except Exception as e:
        print(f"Error listing oldest unread emails: {e}")
        return []



# ------------------------------------------------------------
# Delete old unread emails (1-year cutoff)
# ------------------------------------------------------------
def delete_old_unread_emails(service):
    """
    Deletes unread emails older than 14 year.
    Returns the number of messages deleted.
    """
    years_ago = (datetime.now() - timedelta(days=5110)).strftime("%Y/%m/%d")
    query = f"is:unread before:{years_ago}"

    results = service.users().messages().list(
        userId="me",
        q=query
    ).execute()

    messages = results.get("messages", [])

    if not messages:
        print("No unread emails older than a year found.")
        return 0

    deleted_count = 0

    for message in messages:
        msg_id = message["id"]
        service.users().messages().delete(
            userId="me",
            id=msg_id
        ).execute()

        print(f"Deleted message ID: {msg_id}")
        deleted_count += 1

    return deleted_count
