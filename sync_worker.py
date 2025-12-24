import os
import dotenv
import sqlite3
import datetime
import logging
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Import scraper function
from get_data import get_forex_events

dotenv.load_dotenv()

# --- CONFIGURATION ---
DB_FILE = os.environ.get('DB_FILE')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')


# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def generate_event_id(event_data):
    """
    Creates a unique, consistent ID for Google Calendar.
    Google IDs must be lowercase a-v and 0-9.
    Format: yyyymmdd + currency + simplified_title
    Example: 20251223usdcpidata
    """
    # 1. Clean the title (remove spaces/symbols, keep only letters/numbers)
    clean_title = re.sub(r'[^a-z0-9]', '', event_data['event'].lower())
    
    # 2. Convert time to a rough ID string (using today's date)
    # Note: In a real production app, we would use the actual event date.
    # For this tutorial, we assume the scraper only grabs 'today'.
    today_str = datetime.date.today().strftime("%Y%m%d")
    
    unique_id = f"{today_str}{event_data['currency'].lower()}{clean_title}"
    
    # Google limits IDs to 1024 chars. Truncate if insanely long (rare).
    return unique_id[:100]

def sync_calendars():
    logger.info("--- Starting Sync Job ---")

    # 1. Get the Fresh News
    logger.info("Fetching news from ForexFactory...")
    all_events = get_forex_events()
    
    if not all_events:
        logger.info("No news found today. Exiting.")
        return

    # 2. Get All Users
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    
    logger.info(f"Found {len(users)} users to update.")

    # 3. Process Each User
    for user in users:
        try:
            email = user['email']
            logger.info(f"Syncing for: {email}")

            # --- A. Filter News for this User ---
            user_impacts = user['impact_pref'].split(',') # e.g. ['High', 'Medium']
            user_currencies = user['currencies_pref'].split(',') # e.g. ['USD', 'GBP']
            
            filtered_events = []
            for event in all_events:
                if event['impact'] in user_impacts and event['currency'] in user_currencies:
                    filtered_events.append(event)
            
            if not filtered_events:
                logger.info(f"  No matching events for {email}. Skipping.")
                continue

            # --- B. Authenticate with Google ---
            # We reconstruct the Credentials object using the saved Refresh Token
            creds = Credentials(
                token=None, # We don't have a live access token yet
                refresh_token=user['refresh_token'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                scopes=['https://www.googleapis.com/auth/calendar.events']
            )
            
            # This forces the library to use the refresh_token to get a new access_token
            creds.refresh(Request())

            # --- C. Connect to Calendar API ---
            service = build('calendar', 'v3', credentials=creds)

            # --- D. Add/Update Events ---
            for item in filtered_events:
                # Prepare the event data
                # We need a start/end time. Since ForexFactory gives "8:30am", 
                # we need to parse that into a real datetime.
                # For simplicity in this step, we will create "All Day" events or generic times.
                
                
                event_summary = f"{item['currency']} - {item['event']}"
                event_desc = (
                    f"Impact: {item['impact']}\n"
                    f"Forecast: {item['forecast']}\n"
                    f"Actual: {item['actual']}\n"
                    f"Time: {item['time']}"
                )
                
                ev_id = generate_event_id(item)
                
                event_body = {
                    'id': ev_id, # THE KEY to preventing duplicates
                    'summary': event_summary,
                    'description': event_desc,
                    'start': {'date': datetime.date.today().isoformat()}, # All-day event for now
                    'end': {'date': datetime.date.today().isoformat()},
                    'transparency': 'transparent', # "Available" (doesn't block calendar)
                    'colorId': '11' if item['impact'] == 'High' else '6' # 11=Red, 6=Orange
                }

                try:
                    # Try to insert (create new)
                    service.events().insert(calendarId='primary', body=event_body).execute()
                    logger.info(f"  Created: {event_summary}")
                except Exception as e:
                    # If error is "already exists", we UPDATE it instead
                    if "already exists" in str(e).lower():
                        service.events().update(calendarId='primary', eventId=ev_id, body=event_body).execute()
                        logger.info(f"  Updated: {event_summary}")
                    else:
                        logger.warning(f"  Failed to add event: {e}")

        except Exception as e:
            logger.error(f"Failed to sync user {user['email']}: {e}")

    logger.info("--- Sync Job Complete ---")

if __name__ == "__main__":
    sync_calendars()