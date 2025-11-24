from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime


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

            # subject = next(
            #     (header["value"] for header in headers if header["name"] == "Subject"),
            #     "No Subject"
            # )
            # from_email = next(
            #     (header["value"] for header in headers if header["name"] == "From"),
            #     "Unknown Sender"
            # )

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
    


# def list_oldest_unread_emails(service, limit=50):
#     """
#     Returns the oldest unread emails (up to `limit`).
#     Gmail API does not allow sorting directly, so we:
#       - Fetch unread messages
#       - Retrieve their internalDate
#       - Sort ascending (oldest first)
#       - Return the oldest N
#     """

#     try:
#         # Fetch ALL unread message IDs
#         # but Gmail paginates results — so we fetch until we have at least `limit`
#         messages = []
#         next_page = None

#         while len(messages) < limit:
#             response = service.users().messages().list(
#                 userId="me",
#                 q="is:unread",
#                 pageToken=next_page,
#                 maxResults=100  # larger batch for speed
#             ).execute()

#             msgs = response.get("messages", [])
#             messages.extend(msgs)

#             next_page = response.get("nextPageToken")

#             if not next_page:
#                 break  # no more messages

#         # Fetch metadata for sorting (internalDate)
#         detailed = []
#         for msg in messages[:limit]:  # slice for safety
#             full = service.users().messages().get(
#                 userId="me",
#                 id=msg["id"],
#                 format="metadata",
#                 metadataHeaders=["Subject", "From", "Date"]
#             ).execute()

#             headers = full["payload"]["headers"]
#             subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
#             from_email = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")

#             detailed.append({
#                 "id": full["id"],
#                 "subject": subject,
#                 "from": from_email,
#                 "internalDate": int(full.get("internalDate", 0)),
#             })

#         # Sort by oldest first
#         detailed.sort(key=lambda x: x["internalDate"])

#         # Return the oldest N
#         return detailed[:limit]

#     except Exception as e:
#         print(f"Error listing oldest unread emails: {e}")
#         return []


from datetime import datetime, timedelta

def list_oldest_unread_emails(service, limit=50):
    """
    Returns the oldest unread emails (up to `limit`) including date,
    subject, from, and id.
    """

    try:
        # Step 1: Fetch enough unread message IDs to cover the limit
        messages = []
        next_page = None

        while len(messages) < limit:
            response = service.users().messages().list(
                userId="me",
                q="is:unread",
                pageToken=next_page,
                maxResults=100
            ).execute()

            msgs = response.get("messages", [])
            messages.extend(msgs)

            next_page = response.get("nextPageToken")
            if not next_page:
                break

        # Step 2: Pull metadata (Subject, From, Date, internalDate)
        detailed = []

        for msg in messages[:limit]:
            full = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()

            headers = full["payload"]["headers"]

            subject = next(
                (h["value"] for h in headers if h["name"] == "Subject"),
                "No Subject"
            )
            from_email = next(
                (h["value"] for h in headers if h["name"] == "From"),
                "Unknown Sender"
            )

            # get the Date header
            date_header = next(
                (h["value"] for h in headers if h["name"] == "Date"),
                None
            )

            if date_header:
                try:
                    # Convert header like "Mon, 24 Nov 2025 08:01:17 -0500" → datetime object
                    parsed_dt = parsedate_to_datetime(date_header)
                    date_iso = parsed_dt.isoformat()
                except Exception:
                    parsed_dt = None
                    date_iso = None
            else:
                parsed_dt = None
                date_iso = None

            # Try "Date" header first
            date_str = next(
                (h["value"] for h in headers if h["name"] == "Date"),
                None
            )

            # Parse or fallback to internalDate
            if date_str:
                try:
                    # Try the standard RFC 2822 portion
                    parsed_date = datetime.strptime(
                        date_str[:25], "%a, %d %b %Y %H:%M:%S"
                    )
                    date_final = parsed_date.isoformat()
                except Exception:
                    # Fallback to raw string
                    date_final = date_str
            else:
                internal_ms = int(full.get("internalDate", 0))
                parsed_date = datetime.fromtimestamp(internal_ms / 1000)
                date_final = parsed_date.isoformat()

            # Make internalDate human-readable
            internal_ms = int(full.get("internalDate", 0))
            internal_dt = datetime.fromtimestamp(internal_ms / 1000)
            internal_human = internal_dt.strftime("%a, %d %b %Y %I:%M %p")

            detailed.append({
                "id": full["id"],
                "subject": subject,
                "from": from_email,
                "date": date_final,
                "date": date_header,   # raw header value (recommended for display)
                # "internalDate": int(full.get("internalDate", 0)),
                "date_human": internal_human, # New human-readable format
                "internalDate": internal_ms,  # Raw ms since epoch
            })

        # Step 3: Sort by oldest first
        detailed.sort(key=lambda x: x["internalDate"])

        # Step 4: Return only the oldest `limit`
        return detailed[:limit]

    except Exception as e:
        print(f"Error listing oldest unread emails: {e}")
        return []



# ------------------------------------------------------------
# Delete old unread emails (1-year cutoff)
# ------------------------------------------------------------
def delete_old_unread_emails(service):
    """
    Deletes unread emails older than 1 year.
    Mirrors your FastAPI implementation exactly.
    Returns the number of messages deleted.
    """
    one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y/%m/%d")
    query = f"is:unread before:{one_year_ago}"

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
