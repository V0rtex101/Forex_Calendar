import os
import sqlite3
import logging
import flask
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- Configuration ---
app = flask.Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key_change_in_production')

# Allow OAuth over HTTP for local testing only
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Allow the "Scope has changed" warning to pass without error
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events', 
    'https://www.googleapis.com/auth/userinfo.email'
]
DB_FILE = 'users.db'

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Renders the frontend form for user preferences and login."""
    return '''
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
            <h1 style="text-align: center; color: #333;">Forex Calendar Sync</h1>
            <p style="text-align: center; color: #666;">Sync high-impact economic events directly to your Google Calendar.</p>
            
            <form action="/login" method="post">
                <h3 style="border-bottom: 1px solid #eee; padding-bottom: 10px;">1. Impact Level</h3>
                <label style="margin-right: 15px;"><input type="checkbox" name="impact" value="High" checked> High Impact 🔴</label>
                <label><input type="checkbox" name="impact" value="Medium"> Medium Impact 🟠</label>

                <h3 style="border-bottom: 1px solid #eee; padding-bottom: 10px; margin-top: 20px;">2. Currencies</h3>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <label><input type="checkbox" name="currency" value="USD" checked> USD (US Dollar)</label>
                    <label><input type="checkbox" name="currency" value="EUR" checked> EUR (Euro)</label>
                    <label><input type="checkbox" name="currency" value="GBP" checked> GBP (British Pound)</label>
                    <label><input type="checkbox" name="currency" value="JPY"> JPY (Japanese Yen)</label>
                    <label><input type="checkbox" name="currency" value="CAD"> CAD (Canadian Dollar)</label>
                    <label><input type="checkbox" name="currency" value="AUD"> AUD (Australian Dollar)</label>
                    <label><input type="checkbox" name="currency" value="NZD"> NZD (New Zealand Dollar)</label>
                    <label><input type="checkbox" name="currency" value="CHF"> CHF (Swiss Franc)</label>
                </div>
                
                <div style="text-align: center; margin-top: 30px;">
                    <button type="submit" style="background-color: #4285F4; color: white; padding: 12px 24px; border: none; border-radius: 4px; font-size: 16px; cursor: pointer;">
                        Sign in with Google & Sync
                    </button>
                </div>
            </form>
        </div>
    '''

@app.route('/login', methods=['POST'])
def login():
    """
    Initiates the OAuth 2.0 flow.
    """
    # Capture form data
    flask.session['impact_pref'] = flask.request.form.getlist('impact')
    flask.session['currency_pref'] = flask.request.form.getlist('currency')
    
    # Create flow
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = flask.url_for('callback', _external=True)
    
    # Request offline access
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent' # Forces Google to send the Refresh Token every single time
    )
    
    flask.session['state'] = state
    logger.info("Redirecting user to Google Login...")
    return flask.redirect(authorization_url)

@app.route('/callback')
def callback():
    """
    Handles the OAuth 2.0 callback.
    """
    try:
        state = flask.session['state']
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
        flow.redirect_uri = flask.url_for('callback', _external=True)
        
        # Exchange code for token
        flow.fetch_token(authorization_response=flask.request.url)
        creds = flow.credentials

        # Fetch user email
        user_info_service = build('oauth2', 'v2', credentials=creds)
        user_info = user_info_service.userinfo().get().execute()
        email = user_info['email']

        # Format preferences
        impact_csv = ",".join(flask.session.get('impact_pref', []))
        currency_csv = ",".join(flask.session.get('currency_pref', []))

        # Persist to Database
        with get_db_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO users (email, refresh_token, impact_pref, currencies_pref, last_updated)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (email, creds.refresh_token, impact_csv, currency_csv))
            conn.commit()

        logger.info(f"User {email} successfully registered/updated.")
        return f"<div style='font-family:sans-serif; text-align:center; margin-top:50px;'><h2>Setup Complete!</h2><p>Account: {email}</p><p>You may close this window.</p></div>"

    except Exception as e:
        logger.error(f"Error during callback: {e}")
        return f"<h2>An error occurred during login: {e}</h2>", 500

if __name__ == '__main__':
    logger.info("Starting Flask Server on http://localhost:5000")
    app.run(port=5000, debug=True)