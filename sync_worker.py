import os
import dotenv
import sqlite3
import datetime
import logging
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# --- IMPORTS ---
# Make sure your scraper file is named 'get_data.py' or update this import!
from get_data import get_forex_events

# Load environment variables
dotenv.load_dotenv()

# --- CONFIGURATION ---
DB_FILE = os.environ.get('DB_FILE', 'users.db')
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')

# GLOBAL TIMEZONE: Where is the server running?
# Default to Johannesburg since you are testing on your laptop
SERVER_TIMEZONE = os.environ.get('SCRAPER_TIMEZONE', 'Africa/Johannesburg')

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def generate_event_id(event_data):
    """
    Creates a unique ID.
    Google ONLY allows characters 0-9 and a-v. 
    Letters w, x, y, z are FORBIDDEN.
    """
    # 1. Clean the title: Remove anything that is NOT a-v or 0-9
    raw_id = event_data['event'].lower() + event_data['currency'].lower()
    clean_id = re.sub(r'[^a-v0-9]', '', raw_id)
    
    # 2. Add Date to ensure uniqueness
    today_str = datetime.date.today().strftime("%Y%m%d")
    
    # 3. Combine
    unique_id = f"{today_str}{clean_id}"
    return unique_id[:100]

def parse_event_time(time_str):
    """
    Converts text like "8:30am" into ISO timestamps.
    Returns: (start_iso, end_iso, is_all_day_bool)
    """
    today = datetime.date.today()
    
    # 1. Handle "All Day" or "Tentative"
    if not time_str or "day" in time_str.lower() or "tentative" in time_str.lower():
        return today.isoformat(), today.isoformat(), True

    # 2. Handle specific times (e.g. "8:30am")
    try:
        dt_time = datetime.datetime.strptime(time_str.strip(), "%I:%M%p").time()
        start_dt = datetime.datetime.combine(today, dt_time)
        
        # MINIMAL LOOK: Set End Time equal to Start Time
        # This creates a "0-minute" event that appears as a dot/line
        end_dt = start_dt 
        
        return start_dt.isoformat(), end_dt.isoformat(), False

    except ValueError:
        logger.warning(f"Could not parse time: '{time_str}'. Defaulting to All Day.")
        return today.isoformat(), today.isoformat(), True

def sync_calendars():
    logger.info("--- Starting Sync Job ---")
    logger.info(f"Server Timezone Configured As: {SERVER_TIMEZONE}")

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
            user_impacts = user['impact_pref'].split(',') 
            user_currencies = user['currencies_pref'].split(',') 
            
            filtered_events = []
            for event in all_events:
                if event['impact'] in user_impacts and event['currency'] in user_currencies:
                    filtered_events.append(event)
            
            if not filtered_events:
                logger.info(f"  No matching events for {email}. Skipping.")
                continue

            # --- B. Authenticate with Google ---
            creds = Credentials(
                token=None, 
                refresh_token=user['refresh_token'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                scopes=['https://www.googleapis.com/auth/calendar.events']
            )
            creds.refresh(Request())

            # --- C. Connect to Calendar API ---
            service = build('calendar', 'v3', credentials=creds)

            # --- D. Add/Update Events ---
            for item in filtered_events:
                
                start_iso, end_iso, is_all_day = parse_event_time(item['time'])

                event_summary = f"{item['currency']} - {item['event']}"
                event_desc = (
                    f"Impact: {item['impact']}\n"
                    f"Forecast: {item['forecast']}\n"
                    f"Actual: {item['actual']}\n"
                    f"Time: {item['time']}"
                )
                
                ev_id = generate_event_id(item)
                
                event_body = {
                    'id': ev_id,
                    'summary': event_summary,
                    'description': event_desc,
                    'transparency': 'transparent', # Doesn't block 'Busy' status
                    'colorId': '11' if item['impact'] == 'High' else '6'
                }

                # Use the SERVER_TIMEZONE from .env
                if is_all_day:
                    event_body['start'] = {'date': start_iso}
                    event_body['end'] = {'date': end_iso}
                else:
                    event_body['start'] = {
                        'dateTime': start_iso, 
                        'timeZone': SERVER_TIMEZONE 
                    }
                    event_body['end'] = {
                        'dateTime': end_iso, 
                        'timeZone': SERVER_TIMEZONE 
                    }

                try:
                    # Try to insert (create new)
                    service.events().insert(calendarId='primary', body=event_body).execute()
                    logger.info(f"  Created: {event_summary} at {item['time']}")
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