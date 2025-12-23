import sqlite3
import logging
import os

# Configure logging to display timestamp, log level, and message
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_FILE = 'users.db'

def init_db():
    """
    Initializes the SQLite database structure.
    
    Creates the 'users' table if it does not exist, defining the schema 
    required to store OAuth credentials and user synchronization preferences.
    """
    try:
        # Check if the database file already exists to log the appropriate message
        db_exists = os.path.exists(DB_FILE)

        # Establish connection to the SQLite database
        # The 'with' statement ensures the connection closes automatically
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()

            # Define the schema
            # email: Primary Key (unique identifier for the user)
            # refresh_token: OAuth2 token required for offline access to Google Calendar
            # impact_pref: CSV string of user's impact choices (e.g., "High,Medium")
            # currencies_pref: CSV string of user's currency choices (e.g., "USD,GBP")
            # last_updated: Timestamp to track the last successful sync operation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    refresh_token TEXT NOT NULL,
                    impact_pref TEXT,
                    currencies_pref TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()

        if db_exists:
            logger.info(f"Database '{DB_FILE}' verified. Connection successful.")
        else:
            logger.info(f"Database '{DB_FILE}' created successfully.")

    except sqlite3.Error as e:
        logger.error(f"Critical database error: {e}")
        raise

if __name__ == "__main__":
    init_db()