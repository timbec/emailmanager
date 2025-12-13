from datetime import datetime, timedelta
import time
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



## Mass Deletion by category
def mass_delete_promotions(service, year, category='promotions', limit=None, dry_run=False):
    """
    Deletes ALL unread emails in a specific category for a specific year.
    
    Args:
        year (int): The year to target (e.g., 2018).
        category (str): 'promotions', 'social', 'updates', or 'primary'.
        limit (int): Optional safety cap (e.g., stop after 5000 deletions).
    """
    # 1. Build the specific date range for that year
    start_date = f"{year}/01/01"
    end_date = f"{year + 1}/01/01"
    
    query = f"category:{category} is:unread after:{start_date} before:{end_date}"
    print(f"--- STARTING MASS DELETE ---")
    print(f"Target: {category.upper()} emails from {year}")
    print(f"Query: {query}")

    total_deleted = 0
    next_page = None
    
    while True:
        # Check safety limit
        if limit and total_deleted >= limit:
            print(f"Reached safety limit of {limit}. Stopping.")
            break

        # 2. Fetch IDs only (lightweight)
        # batchDelete only accepts 1000 IDs at a time, so we fetch 1000 max.
        results = service.users().messages().list(
            userId="me",
            q=query,
            pageToken=next_page,
            maxResults=1000, 
            fields="nextPageToken,messages(id)"
        ).execute()

        messages = results.get("messages", [])
        
        if not messages:
            print("No more messages found matching criteria!")
            break

        # 3. Extract IDs for the batch
        batch_ids = [msg['id'] for msg in messages]
        
        # 4. EXECUTE BATCH DELETE
        print(f"Deleting batch of {len(batch_ids)} emails...")
        try:
            service.users().messages().batchDelete(
                userId="me",
                body={"ids": batch_ids}
            ).execute()
            
            total_deleted += len(batch_ids)
            print(f"Total deleted so far: {total_deleted}")
            
        except Exception as e:
            print(f"Error during batch delete: {e}")
            break

        # 5. Check if there are more pages
        next_page = results.get("nextPageToken")
        if not next_page:
            break
            
        # Optional: Sleep briefly to be nice to the API
        time.sleep(0.5)

    print(f"--- DONE. Deleted {total_deleted} emails from {year}. ---")
    return total_deleted


def batch_trash_emails(service, message_ids):
    """
    Moves a list of message IDs to the Trash efficiently.
    Uses Google's BatchHttpRequest to avoid making 1000 separate network calls.
    """
    if not message_ids:
        return 0

    # This callback just suppresses errors (like if an email was already deleted)
    def callback(request_id, response, exception):
        if exception:
            print(f"Error trashing message {request_id}: {exception}")

    batch = service.new_batch_http_request(callback=callback)

    for msg_id in message_ids:
        # We queue up the 'trash' command instead of executing it immediately
        batch.add(
            service.users().messages().trash(userId='me', id=msg_id),
            request_id=msg_id
        )

    # Fire all queued commands at once
    batch.execute()
    
    return len(message_ids)



# core/utils.py

import time
from collections import Counter

# Make sure 'dry_run' is in this line:
def mass_delete_emails(service, year, category='promotions', limit=None, dry_run=True):
    
    # 1. Build Query
    start_date = f"{year}/01/01"
    end_date = f"{year + 1}/01/01"
    query = f"category:{category} is:unread after:{start_date} before:{end_date}"
    
    print(f"\n{'='*40}")
    print(f"MODE: {'DRY RUN (Analysis Only)' if dry_run else 'DESTRUCTIVE (Deleting)'}")
    print(f"Query: {query}")
    print(f"{'='*40}\n")

    # If Dry Run, we only fetch a small sample to generate a report
    fetch_limit = 50 if dry_run else 1000
    
    total_processed = 0
    next_page = None
    
    while True:
        # Check global limit
        if limit and total_processed >= limit:
            print(f"Reached limit of {limit}.")
            break

        # 2. Fetch IDs
        results = service.users().messages().list(
            userId="me",
            q=query,
            pageToken=next_page,
            maxResults=fetch_limit, 
            fields="nextPageToken,messages(id)"
        ).execute()

        messages = results.get("messages", [])
        
        if not messages:
            print("No emails found matching criteria.")
            break

        # --- DRY RUN LOGIC ---
        if dry_run:
            print(f"Analyzing sample of {len(messages)} emails...")
            senders = []
            subjects = []
            
            for msg in messages:
                # We need to fetch headers to see the Sender
                meta = service.users().messages().get(
                    userId="me", id=msg['id'], format="metadata", 
                    metadataHeaders=['From', 'Subject']
                ).execute()
                
                headers = meta['payload']['headers']
                frm = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
                sub = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
                
                # Clean up sender name
                sender_name = frm.split('<')[0].strip().replace('"', '')
                senders.append(sender_name)
                subjects.append(f"{sender_name}: {sub[:30]}...")

            print(f"\n--- SENDER REPORT ({year}) ---")
            for name, count in Counter(senders).most_common(10):
                print(f"{count}x  From: {name}")
            
            print("\n--- SAMPLE SUBJECTS ---")
            for s in subjects[:5]:
                print(f" - {s}")
                
            print(f"\n[!] Dry Run Complete. To delete, run with dry_run=False")
            return 0 # Stop here

        # --- DELETION LOGIC (Using Trash) ---
        else:
            # Use the permanent batchDelete OR the batch_trash helper we made
            batch_ids = [msg['id'] for msg in messages]
            print(f"Deleting batch of {len(batch_ids)} emails...")
            
            try:
                service.users().messages().batchDelete(
                    userId="me",
                    body={"ids": batch_ids}
                ).execute()
                
                total_processed += len(batch_ids)
                print(f"Total deleted so far: {total_processed}")
            except Exception as e:
                print(f"Error: {e}")
                break

        next_page = results.get("nextPageToken")
        if not next_page:
            break
            
        time.sleep(1) # Safety pause

    return total_processed