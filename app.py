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

# Import database helpers
from database import get_db_connection, init_db

# Load environment variables
dotenv.load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_key')

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE = os.path.join(BASE_DIR, 'client_secret.json')

# FIXED: Added email and openid scopes so we can actually get the user's email
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

API_SECRET_KEY = os.environ.get('API_SECRET_KEY')

# Allow HTTP for local testing
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Initialize DB
init_db()

# --- WEB ROUTES ---

@app.route('/')
def index():
    if 'credentials' not in session:
        # Styled Login Page
        return render_template_string("""
        <html>
        <head>
            <title>Forex Sync - Login</title>
            <style>
                body { font-family: -apple-system, sans-serif; background: #1a1a1a; color: #fff; display: flex; height: 100vh; justify-content: center; align-items: center; margin: 0; }
                .card { background: #2d2d2d; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); text-align: center; width: 300px; }
                h1 { font-size: 1.5rem; margin-bottom: 1rem; }
                button { background: #4285F4; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 1rem; cursor: pointer; width: 100%; }
                button:hover { background: #357ae8; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Forex Calendar Sync</h1>
                <p style="color: #aaa; margin-bottom: 2rem;">Automate your trading schedule.</p>
                <a href="/authorize"><button>Sign In with Google</button></a>
            </div>
        </body>
        </html>
        """)
    return redirect(url_for('dashboard'))

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES)

    # FIXED: Force HTTPS to prevent Redirect URI Mismatch on PythonAnywhere
    flow.redirect_uri = url_for('oauth2callback', _external=True).replace('http:', 'https:')

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

    # FIXED: Force HTTPS here too
    flow.redirect_uri = url_for('oauth2callback', _external=True).replace('http:', 'https:')

    authorization_response = request.url
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

    # Now this will work because we added the correct SCOPES
    service = build('oauth2', 'v2', credentials=creds)
    user_info = service.userinfo().get().execute()
    email = user_info['email']
    session['email'] = email

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
    # 1. Session Safety Check
    if 'email' not in session:
        session.clear()
        return redirect(url_for('index'))

    email = session['email']
    conn = get_db_connection()
    saved = False  # Default: No popup

    # 2. Handle Save
    if request.method == 'POST':
        impacts = ",".join(request.form.getlist('impact'))
        currencies = ",".join(request.form.getlist('currency'))
        conn.execute('UPDATE users SET impact_pref = ?, currencies_pref = ? WHERE email = ?',
                     (impacts, currencies, email))
        conn.commit()
        saved = True # Trigger the popup

    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()

    # 3. Render UI with Popup Logic
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #1a1a1a; color: #e0e0e0; margin: 0; padding: 20px; display: flex; justify-content: center; min-height: 100vh; }
            .container { background-color: #2d2d2d; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); width: 100%; max-width: 450px; }
            h1 { margin-top: 0; color: #fff; font-size: 1.8rem; }
            p { color: #aaa; margin-bottom: 2rem; }
            h3 { color: #4CAF50; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 1.5rem; border-bottom: 1px solid #444; padding-bottom: 5px; }
            label { display: flex; align-items: center; margin: 12px 0; cursor: pointer; font-size: 1rem; transition: color 0.2s; }
            label:hover { color: #fff; }
            input[type="checkbox"] { margin-right: 12px; transform: scale(1.2); accent-color: #4CAF50; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
            button { background-color: #4CAF50; color: white; padding: 14px; border: none; border-radius: 8px; font-size: 1rem; font-weight: bold; cursor: pointer; width: 100%; margin-top: 30px; transition: background 0.2s; }
            button:hover { background-color: #45a049; }
            .status { margin-top: 20px; font-size: 0.85rem; color: #666; text-align: center; }

            /* --- POPUP STYLES --- */
            #toast {
                visibility: hidden;
                min-width: 250px;
                background-color: #333;
                color: #fff;
                text-align: center;
                border-radius: 50px;
                padding: 16px;
                position: fixed;
                z-index: 1;
                left: 50%;
                bottom: 30px;
                transform: translateX(-50%);
                box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                border: 1px solid #4CAF50;
                font-weight: 500;
                opacity: 0;
                transition: opacity 0.5s, bottom 0.5s;
            }

            #toast.show {
                visibility: visible;
                opacity: 1;
                bottom: 50px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Settings</h1>
            <p>User: {{ user['email'] }}</p>

            <form method="post">
                <h3>Impact Level</h3>
                <label><input type="checkbox" name="impact" value="High" {% if 'High' in user['impact_pref'] %}checked{% endif %}> High Impact</label>
                <label><input type="checkbox" name="impact" value="Medium" {% if 'Medium' in user['impact_pref'] %}checked{% endif %}> Medium Impact</label>

                <h3>Currencies</h3>
                <div class="grid">
                    {% for curr in ['USD','EUR','GBP','JPY','AUD','CAD','CHF','NZD'] %}
                         <label><input type="checkbox" name="currency" value="{{ curr }}" {% if curr in user['currencies_pref'] %}checked{% endif %}> {{ curr }}</label>
                    {% endfor %}
                </div>

                <button type="submit">Save Preferences</button>
            </form>
            <div class="status">Sync is active. Updates occur hourly.</div>
        </div>

        <div id="toast">✅ Changes Saved Successfully!</div>

        <script>
            // This runs only if Python says 'saved=True'
            {% if saved %}
            window.onload = function() {
                var x = document.getElementById("toast");
                x.className = "show";
                // Hide it after 3 seconds (3000ms)
                setTimeout(function(){ x.className = x.className.replace("show", ""); }, 3000);
            };
            {% endif %}
        </script>
    </body>
    </html>
    """
    # Pass the 'saved' variable to the template
    return render_template_string(html, user=user, saved=saved)

# --- API ENDPOINT ---
@app.route('/api/receive_news', methods=['POST'])
def receive_news():
    key = request.headers.get('X-API-KEY')
    if key != API_SECRET_KEY:
        return jsonify({"error": "Forbidden"}), 403

    events = request.json
    if not events:
        return jsonify({"message": "No events received"}), 200

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()

    count = 0
    errors = []

    try:
        with open(CLIENT_SECRETS_FILE) as f:
            client_config = json.load(f)
            web_config = client_config.get('web', client_config.get('installed'))
    except Exception as e:
        return jsonify({"error": f"Config load failed: {str(e)}"}), 500

    for user in users:
        try:
            if not user['impact_pref'] or not user['currencies_pref']: continue

            user_impacts = user['impact_pref'].split(',')
            user_currencies = user['currencies_pref'].split(',')

            my_events = [e for e in events if e['impact'] in user_impacts and e['currency'] in user_currencies]
            if not my_events: continue

            creds = Credentials(
                token=None, refresh_token=user['refresh_token'],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=web_config['client_id'], client_secret=web_config['client_secret'],
                scopes=['https://www.googleapis.com/auth/calendar.events']
            )
            creds.refresh(Request())
            service = build('calendar', 'v3', credentials=creds)

            for item in my_events:
                raw_id = f"{datetime.date.today()}{item['currency']}{item['event']}"
                uid = ''.join(c for c in raw_id if c.isalnum()).lower()[:50]
                dt_time = datetime.datetime.strptime(item['time'].strip(), "%I:%M%p").time()
                start_dt = datetime.datetime.combine(datetime.date.today(), dt_time)

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
                except:
                    service.events().update(calendarId='primary', eventId=uid, body=body).execute()

            count += 1
        except Exception as e:
            errors.append(f"User {user['email']}: {str(e)}")

    return jsonify({"status": "success", "users_synced": count, "errors": errors}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)