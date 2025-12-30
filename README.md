📈 Forex Factory to Google Calendar Sync
Automate your trading schedule. This full-stack application scrapes high-impact economic news from ForexFactory and syncs it directly to your Google Calendar. It handles timezone conversions, prevents duplicates, and allows users to filter by currency and impact level.

✨ Features
Automated Scraper: Fetches daily economic news (CPI, NFP, GDP, etc.) from ForexFactory using a headless Chrome browser.

Smart Sync: Prevents duplicate events and updates existing ones if data changes.

User Dashboard: Web interface to log in with Google and configure preferences (e.g., "Only show USD & GBP High Impact news").

Timezone Aware: Automatically converts news times from the server location (e.g., New York) to the user's local Google Calendar time.

Minimalist UI: Events appear as 0-minute "markers" on the calendar to avoid cluttering your schedule.

🛠️ Tech Stack
Frontend/Server: Flask (Python)

Database: SQLite (Stores user preferences and OAuth tokens)

Scraping: Selenium & Webdriver Manager (Headless Chrome)

APIs: Google OAuth2 & Google Calendar API

🚀 Setup Guide (Local Machine)
1. Prerequisites
Python 3.x installed.

Google Chrome installed.

A Google Cloud Project with the Calendar API enabled.

2. Installation
Clone the repository and install dependencies:

Bash

git clone https://github.com/yourusername/forex-calendar-sync.git
cd forex-calendar-sync

# Create virtual environment (Optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install libraries
pip install pandas selenium webdriver-manager google-auth google-auth-oauthlib google-api-python-client python-dotenv flask
3. Google Cloud Configuration
Go to the Google Cloud Console.

Create a Project and enable the Google Calendar API.

Go to Credentials -> Create Credentials -> OAuth Client ID.

Application Type: Web Application.

Redirect URI: http://localhost:5000/callback (for local testing).

Download the JSON file, rename it to client_secret.json, and place it in the project root.

4. Environment Variables
Create a file named .env in the project folder and add the following:

Ini, TOML

# Database Config
DB_FILE=users.db

# Server Timezone (Where the script is running)
SCRAPER_TIMEZONE=Africa/Johannesburg

# Flask Security
FLASK_SECRET_KEY=super_secret_random_string
5. Run the Application
Step A: Start the Website (Dashboard)

Bash

python app.py
Visit http://localhost:5000 in your browser.

Log in with Google and save your preferences.

Step B: Run the Sync Worker Open a new terminal and run:

Bash

python sync_worker.py
The script will scrape ForexFactory and populate your Google Calendar based on your saved settings.

☁️ Deployment (PythonAnywhere)
This project is optimized for deployment on PythonAnywhere (Free Tier).

Upload Files: Upload app.py, sync_worker.py, get_data.py, client_secret.json, and .env.

Update .env: Set SCRAPER_TIMEZONE=America/New_York (or UTC) depending on the server location.

Google Credentials: Update your Google Cloud Console Redirect URI to https://yourusername.pythonanywhere.com/callback.

Schedule Task: Set a daily task to run python3 sync_worker.py at 06:00 UTC.

Note: The scraper automatically detects the PythonAnywhere environment and switches to the correct headless Chrome settings.

📂 Project Structure
app.py - The Flask web server (Login & Dashboard).

sync_worker.py - The logic that reads the DB, runs the scraper, and talks to Google.

get_data.py - The Selenium scraper that browses ForexFactory.

users.db - SQLite database (Created automatically on first run).

client_secret.json - Your private Google API keys (DO NOT COMMIT THIS).

⚠️ Disclaimer

This tool is for educational and personal use. ForexFactory data is owned by Fair Economy, Inc. Ensure you comply with their terms of service regarding automated access.

Created by Fulufhelo Mulaudzi
