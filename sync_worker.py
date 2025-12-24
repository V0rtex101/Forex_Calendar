import os
import dotenv
import sqlite3
import datetime
import logging
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Import scraper function (kept as get_data per your code)
from get_data import get_forex_events

# Load environment variables
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
    CRITICAL: Google ONLY allows characters 0-9 and a-v. 
    Letters w, x, y, z are FORBIDDEN and will cause Error 400.
    """
    # 1. Clean the title: Remove anything that is NOT a-v or 0-9
    # We change the regex from a-z to a-v
    raw_id = event_data['event'].lower() + event_data['currency'].lower()
    clean_id = re.sub(r'[^a-v0-9]', '', raw_id)
    
    # 2. Add Date to ensure uniqueness
    today_str = datetime.date.today().strftime("%Y%m%d")
    
    # 3. Combine
    unique_id = f"{today_str}{clean_id}"
    
    # Google limits IDs to 1024 chars. Truncate if insanely long.
    return unique_id[:100]


def parse_event_time(time_str):
    """
    Converts text like "8:30am" into real ISO timestamps.
    Returns: (start_iso, end_iso, is_all_day_bool)
    """
    today = datetime.date.today()
    
    # 1. Handle "All Day" or "Tentative"
    # If time is missing or vague, default to All Day
    if not time_str or "day" in time_str.lower() or "tentative" in time_str.lower():
        return today.isoformat(), today.isoformat(), True

    # 2. Handle specific times (e.g. "8:30am")
    try:
        # Parse "8:30am"
        dt_time = datetime.datetime.strptime(time_str.strip(), "%I:%M%p").time()
        
        # Combine with today's date
        start_dt = datetime.datetime.combine(today, dt_time)
        
        # Assume event lasts 1 hour
        end_dt = start_dt + datetime.timedelta(hours=1)
        
        # Return full ISO format
        return start_dt.isoformat(), end_dt.isoformat(), False

    except ValueError:
        logger.warning(f"Could not parse time: '{time_str}'. Defaulting to All Day.")
        return today.isoformat(), today.isoformat(), True

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
                
                # 1. Parse the time using our new helper function
                start_iso, end_iso, is_all_day = parse_event_time(item['time'])

                event_summary = f"{item['currency']} - {item['event']}"
                event_desc = (
                    f"Impact: {item['impact']}\n"
                    f"Forecast: {item['forecast']}\n"
                    f"Actual: {item['actual']}\n"
                    f"Time: {item['time']}"
                )
                
                ev_id = generate_event_id(item)
                
                # 2. Construct the Event Body
                event_body = {
                    'id': ev_id,
                    'summary': event_summary,
                    'description': event_desc,
                    'transparency': 'transparent', # Doesn't block 'Busy' status
                    'colorId': '11' if item['impact'] == 'High' else '6'
                }

                # 3. Assign Time (Date vs DateTime)
                if is_all_day:
                    event_body['start'] = {'date': start_iso}
                    event_body['end'] = {'date': end_iso}
                else:
                    # We must specify the Time Zone for non-all-day events.
                    # Using 'Africa/Johannesburg' since that's where I'm located.
                    event_body['start'] = {
                        'dateTime': start_iso, 
                        'timeZone': 'Africa/Johannesburg' 
                    }
                    event_body['end'] = {
                        'dateTime': end_iso, 
                        'timeZone': 'Africa/Johannesburg'
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