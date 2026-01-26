# Forex Calendar Sync 📉➡️📅

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated-yellow.svg)
![Status](https://img.shields.io/badge/Status-Production-success.svg)

**Forex Calendar Sync** is a hybrid-cloud application that automates the tracking of economic news events. It scrapes high-impact financial data from ForexFactory and synchronizes it directly to your Google Calendar, filtering by currency and impact level.

## 🚀 Features

* **Automated Scraper:** Runs hourly via GitHub Actions to fetch real-time data.
* **Smart Updates:** Updates calendar events with "Actual" data values as soon as news is released.
* **User Dashboard:** A secure web interface to manage sync preferences.
* **Custom Filters:**
    * **Impact:** Select High (Red) or Medium (Orange) impact events.
    * **Currencies:** Filter by major pairs (USD, EUR, GBP, JPY, etc.).
* **Security:** Uses Google OAuth 2.0 for secure, token-based authentication (no passwords stored).

---

## 🏗 System Architecture

This project utilizes a **Hybrid Cloud** architecture to maximize uptime and minimize costs.

1.  **Data Collection Service (GitHub Actions):**
    * Runs `sender.py` on a scheduled cron job (hourly).
    * Uses Selenium to scrape specific financial data points from ForexFactory.
    * Transmits the data payload securely to the Backend Server via a REST API.

2.  **Backend Server (PythonAnywhere):**
    * Hosts the Flask Application (`app.py`).
    * Manages the SQLite database of users, preferences, and OAuth refresh tokens.
    * Validates incoming data and distributes relevant events to subscribed users.

3.  **External Integration (Google Calendar API):**
    * Receives API calls from the Backend Server to create or update events on the user's primary calendar.
    * Ensures data is formatted correctly for the user's specific timezone.

---

## 🛠️ Installation & Local Setup

### Prerequisites
* Python 3.10+
* A Google Cloud Project with Calendar API enabled.
* `client_secret.json` from Google Cloud Console.

### 1. Clone the Repository

git clone [https://github.com/your-username/forex-calendar-sync.git](https://github.com/your-username/forex-calendar-sync.git)
cd forex-calendar-sync
### 2. Install Dependencies
pip install -r requirements.txt
### 3. Environment Configuration
Create a .env file in the root directory:

Ini, TOML
#### Flask Security
FLASK_SECRET_KEY=your_random_string_here

#### API Security (Must match between Server and Scraper)
API_SECRET_KEY=your_secure_api_password
### 4. Run Locally
python app.py

The web dashboard will launch at http://localhost:5000.
Note: You must add http://localhost:5000/callback to your Google Cloud Redirect URIs for local testing.

## ☁️ Deployment Guide
### Part 1: The Server (PythonAnywhere)
Upload app.py, database.py, requirements.txt, and .env to PythonAnywhere.

Upload your Google client_secret.json to the same directory.

Set up a virtual environment and install dependencies.

Configure the WSGI file to point to your app.

Important: Add https://your-username.pythonanywhere.com/callback to Google Cloud Redirect URIs.

### Part 2: The Scraper (GitHub Actions)
Ensure .github/workflows/hourly_scan.yml is present in the repository.

Go to repository Settings > Secrets and variables > Actions.

Add a new secret named API_SECRET_KEY.

Set the value to match the password in your server's .env file.

## 🛡️ Security & Privacy
OAuth 2.0: We never see or store your Google password. We only store a refresh_token to access the calendar.

Data Isolation: User data is stored in a local SQLite database (users.db) and is not shared with third parties.

Account Deletion: Users can unsubscribe and delete all their data immediately via the Dashboard "Danger Zone."