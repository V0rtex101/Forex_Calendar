import os
import datetime
import json
import logging
import dotenv
from flask import Flask, redirect, url_for, session, render_template_string, request, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Import database helpers from my module
from database import get_db_connection, init_db 

# Load environment variables
dotenv.load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key')

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'client_secret.json')
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
API_SECRET_KEY = os.environ.get('API_SECRET_KEY')

# Allow HTTP for local testing/development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Initialize DB structure on startup
init_db()

# --- WEB ROUTES ---

@app.route('/')
def index():
    if 'credentials' not in session:
        return '<a href="/authorize"><button>Sign In with Google</button></a>'
    return redirect(url_for('dashboard'))

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('oauth2callback', _external=True)
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('oauth2callback', _external=True)

    authorization_response = request.url
    # Fix for http vs https mismatch on proxies
    if request.headers.get('X-Forwarded-Proto') == 'https':
        authorization_response = authorization_response.replace('http:', 'https:')

    flow.fetch_token(authorization_response=authorization_response)
    creds = flow.credentials
    
    session['credentials'] = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    
    service = build('oauth2', 'v2', credentials=creds)
    user_info = service.userinfo().get().execute()
    email = user_info['email']
    session['email'] = email

    # Store user in database
    conn = get_db_connection()
    existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    
    if not existing_user:
        conn.execute('INSERT INTO users (email, refresh_token) VALUES (?, ?)', 
                     (email, creds.refresh_token))
    else:
        if creds.refresh_token:
            conn.execute('UPDATE users SET refresh_token = ? WHERE email = ?', 
                         (creds.refresh_token, email))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'email' not in session:
        return redirect(url_for('index'))
    
    email = session['email']
    conn = get_db_connection()
    
    if request.method == 'POST':
        # Default to empty string if no checkboxes selected
        impacts = ",".join(request.form.getlist('impact'))
        currencies = ",".join(request.form.getlist('currency'))
        conn.execute('UPDATE users SET impact_pref = ?, currencies_pref = ? WHERE email = ?',
                     (impacts, currencies, email))
        conn.commit()
    
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    
    html = """
    <h1>Welcome {{ user['email'] }}</h1>
    <form method="post">
        <h3>Filter Impacts:</h3>
        <label><input type="checkbox" name="impact" value="High" {% if 'High' in user['impact_pref'] %}checked{% endif %}> High</label>
        <label><input type="checkbox" name="impact" value="Medium" {% if 'Medium' in user['impact_pref'] %}checked{% endif %}> Medium</label>
        <br>
        <h3>Filter Currencies:</h3>
        {% for curr in ['USD','EUR','GBP','JPY','AUD','CAD','CHF','NZD'] %}
             <label><input type="checkbox" name="currency" value="{{ curr }}" {% if curr in user['currencies_pref'] %}checked{% endif %}> {{ curr }}</label>
        {% endfor %}
        <br><br>
        <button type="submit">Save Preferences</button>
    </form>
    <p>Your calendar will sync automatically every morning.</p>
    """
    return render_template_string(html, user=user)

# --- API ENDPOINTS ---

@app.route('/api/receive_news', methods=['POST'])
def receive_news():
    # Verify the request comes from our GitHub Action
    key = request.headers.get('X-API-KEY')
    if key != API_SECRET_KEY:
        return jsonify({"error": "Forbidden: Invalid API Key"}), 403

    events = request.json
    if not events:
        return jsonify({"message": "No events received"}), 200

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()

    count = 0
    errors = []

    # Read client config for OAuth flow
    with open(CLIENT_SECRETS_FILE) as f:
        client_config = json.load(f)
        web_config = client_config.get('web', client_config.get('installed'))

    for user in users:
        try:
            # Skip if user has no preferences set
            if not user['impact_pref'] or not user['currencies_pref']:
                continue

            user_impacts = user['impact_pref'].split(',')
            user_currencies = user['currencies_pref'].split(',')
            
            my_events = [e for e in events if e['impact'] in user_impacts and e['currency'] in user_currencies]
            if not my_events: continue

            creds = Credentials(
                token=None, 
                refresh_token=user['refresh_token'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=web_config['client_id'],
                client_secret=web_config['client_secret'],
                scopes=['https://www.googleapis.com/auth/calendar.events']
            )
            creds.refresh(Request())
            service = build('calendar', 'v3', credentials=creds)

            for item in my_events:
                # Generate unique ID for the event
                raw_id = f"{datetime.date.today()}{item['currency']}{item['event']}"
                uid = ''.join(c for c in raw_id if c.isalnum()).lower()[:50]

                # Parse Time
                dt_time = datetime.datetime.strptime(item['time'].strip(), "%I:%M%p").time()
                start_dt = datetime.datetime.combine(datetime.date.today(), dt_time)
                
                # 0-Minute Event (Visual Marker)
                body = {
                    'id': uid,
                    'summary': f"{item['currency']} - {item['event']}",
                    'description': f"Impact: {item['impact']}\nForecast: {item['forecast']}\nActual: {item['actual']}",
                    'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Africa/Johannesburg'},
                    'end': {'dateTime': start_dt.isoformat(), 'timeZone': 'Africa/Johannesburg'},
                    'colorId': '11' if item['impact'] == 'High' else '6'
                }
                
                try:
                    service.events().insert(calendarId='primary', body=body).execute()
                except Exception:
                    # Update existing event if ID conflict occurs
                    service.events().update(calendarId='primary', eventId=uid, body=body).execute()
            
            count += 1
        except Exception as e:
            errors.append(f"User {user['email']}: {str(e)}")

    return jsonify({"status": "success", "users_synced": count, "errors": errors}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)