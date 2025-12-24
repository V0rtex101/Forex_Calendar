import os
import sqlite3
import logging
import flask
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# --- CONFIGURATION ---
app = flask.Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'super_secret_key_for_session')

# Security Settings for Localhost
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
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
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# --- HELPER: Decides if a box should be checked ---
def is_checked(value, csv_string):
    if not csv_string: return ""
    return "checked" if value in csv_string.split(',') else ""

# --- ROUTE 1: The Login Gate ---
@app.route('/')
def index():
    # If already logged in, go straight to dashboard
    if 'user_email' in flask.session:
        return flask.redirect('/dashboard')

    return '''
        <div style="font-family: Arial, sans-serif; text-align: center; margin-top: 100px;">
            <h1>Forex Calendar Sync</h1>
            <p>Sign in to manage your news preferences.</p>
            <a href="/login">
                <button style="background-color: #4285F4; color: white; padding: 15px 30px; border: none; border-radius: 5px; font-size: 18px; cursor: pointer;">
                    Sign in with Google
                </button>
            </a>
        </div>
    '''

# --- ROUTE 2: Google Auth Flow ---
@app.route('/login')
def login():
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = flask.url_for('callback', _external=True)
    
    # We use prompt='consent' to ensure we get a Refresh Token if we don't have one
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    flask.session['state'] = state
    return flask.redirect(authorization_url)

@app.route('/callback')
def callback():
    try:
        state = flask.session['state']
        flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
        flow.redirect_uri = flask.url_for('callback', _external=True)
        
        flow.fetch_token(authorization_response=flask.request.url)
        creds = flow.credentials

        # Get User Email
        user_info_service = build('oauth2', 'v2', credentials=creds)
        user_info = user_info_service.userinfo().get().execute()
        email = user_info['email']

        # Database Logic
        conn = get_db_connection()
        
        # 1. Check if user exists
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        
        if user:
            # User exists: Update token ONLY if Google gave us a new one
            new_token = creds.refresh_token if creds.refresh_token else user['refresh_token']
            conn.execute("UPDATE users SET refresh_token = ? WHERE email = ?", (new_token, email))
        else:
            # New User: Insert with defaults
            conn.execute('''
                INSERT INTO users (email, refresh_token, impact_pref, currencies_pref, last_updated)
                VALUES (?, ?, 'High', 'USD,EUR,GBP', CURRENT_TIMESTAMP)
            ''', (email, creds.refresh_token))
        
        conn.commit()
        conn.close()

        # Log the user in (Save to Session)
        flask.session['user_email'] = email
        return flask.redirect('/dashboard')

    except Exception as e:
        logger.error(f"Login failed: {e}")
        return f"Error: {e}"

# --- ROUTE 3: The Dashboard (User Interface) ---
@app.route('/dashboard')
def dashboard():
    # Security Check: Are they logged in?
    if 'user_email' not in flask.session:
        return flask.redirect('/')
    
    email = flask.session['user_email']
    
    # Fetch current settings from DB
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not user:
        return "Error: User not found in database."

    # Parse settings for the UI
    impacts = user['impact_pref'] or ""
    currencies = user['currencies_pref'] or ""

    return f'''
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3>⚙️ Settings for {email}</h3>
                <a href="/logout" style="color:red; text-decoration:none;">Logout</a>
            </div>
            <hr>
            
            <form action="/save_settings" method="post">
                <h4>1. Impact Level</h4>
                <label><input type="checkbox" name="impact" value="High" {is_checked('High', impacts)}> High Impact 🔴</label><br>
                <label><input type="checkbox" name="impact" value="Medium" {is_checked('Medium', impacts)}> Medium Impact 🟠</label>

                <h4>2. Currencies</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <label><input type="checkbox" name="currency" value="USD" {is_checked('USD', currencies)}> USD 🇺🇸</label>
                    <label><input type="checkbox" name="currency" value="EUR" {is_checked('EUR', currencies)}> EUR 🇪🇺</label>
                    <label><input type="checkbox" name="currency" value="GBP" {is_checked('GBP', currencies)}> GBP 🇬🇧</label>
                    <label><input type="checkbox" name="currency" value="JPY" {is_checked('JPY', currencies)}> JPY 🇯🇵</label>
                    <label><input type="checkbox" name="currency" value="CAD" {is_checked('CAD', currencies)}> CAD 🇨🇦</label>
                    <label><input type="checkbox" name="currency" value="AUD" {is_checked('AUD', currencies)}> AUD 🇦🇺</label>
                    <label><input type="checkbox" name="currency" value="NZD" {is_checked('NZD', currencies)}> NZD 🇳🇿</label>
                    <label><input type="checkbox" name="currency" value="CHF" {is_checked('CHF', currencies)}> CHF 🇨🇭</label>
                </div>
                
                <br>
                <button type="submit" style="background-color: #0F9D58; color: white; padding: 12px 24px; border: none; border-radius: 4px; font-size: 16px; cursor: pointer; width: 100%;">
                    Save Changes
                </button>
            </form>
        </div>
    '''

# --- ROUTE 4: Save Actions ---
@app.route('/save_settings', methods=['POST'])
def save_settings():
    if 'user_email' not in flask.session:
        return flask.redirect('/')

    email = flask.session['user_email']
    
    # Get lists from form
    impact_list = flask.request.form.getlist('impact')
    currency_list = flask.request.form.getlist('currency')
    
    # Join into strings
    impact_str = ",".join(impact_list)
    currency_str = ",".join(currency_list)

    # Update DB
    conn = get_db_connection()
    conn.execute("UPDATE users SET impact_pref = ?, currencies_pref = ? WHERE email = ?", 
                 (impact_str, currency_str, email))
    conn.commit()
    conn.close()

    return flask.redirect('/dashboard')

@app.route('/logout')
def logout():
    flask.session.clear()
    return flask.redirect('/')

if __name__ == '__main__':
    app.run(port=5000, debug=True)