import os
import requests
import json
from get_data import get_forex_events

# CONFIGURATION
# 1. Your PythonAnywhere "Secret Door" URL
# REPLACE 'fu1u' with your actual username
TARGET_URL = "https://fu1u.pythonanywhere.com/api/receive_news"

# 2. Get the password from GitHub Secrets
API_SECRET = os.environ.get("API_SECRET_KEY")

if not API_SECRET:
    print("Error: API_SECRET_KEY not found in environment variables.")
    exit(1)

print("--- Step 1: Scraping ForexFactory ---")
# This uses your existing get_data.py script
events = get_forex_events()

if not events:
    print("No high/medium impact events found today. Exiting.")
    exit(0)

print(f"--- Step 2: Sending {len(events)} events to PythonAnywhere ---")

# Prepare the data package
headers = {
    "Content-Type": "application/json",
    "X-API-KEY": API_SECRET  # This is the password knock
}

try:
    # Send the POST request (The "Handover")
    response = requests.post(TARGET_URL, json=events, headers=headers)
    
    # 
    if response.status_code == 200:
        print("Success! Server responded:")
        print(json.dumps(response.json(), indent=2))
    elif response.status_code == 403:
        print("Error 403: Forbidden. Did you set the correct API Password?")
        print(response.text)
    else:
        print(f"Error {response.status_code}: {response.text}")
        
except Exception as e:
    print(f"Connection Failed: {e}")