import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

def get_forex_events():
    # --- 1. SETUP ---
    chrome_options = Options()
    
    # "Headless" mode means the browser runs in the background (invisible).
    # If you want to see it work, comment out the next line.
    #chrome_options.add_argument("--headless") 
    
    # These arguments make it more stable on servers/Windows
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    # Fake a user agent so ForexFactory thinks we are a real person instead of a bot
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # Install/Update Chrome Driver automatically
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    events = []
    
    try:
        # --- 2. FETCH PAGE ---
        # We go to today's calendar
        driver.get("https://www.forexfactory.com/calendar?day=today")
        time.sleep(3) # Wait for page to load

        # --- 3. EXTRACT DATA ---
        # Find all rows that look like calendar events
        rows = driver.find_elements(By.XPATH, "//tr[contains(@class, 'calendar__row')]")
        
        for row in rows:
            try:
                # Get Event Name. If empty, it's just a spacer line -> skip it.
                event_name = row.find_element(By.CLASS_NAME, "calendar__event-title").text
                if not event_name: 
                    continue

                # Get basic info
                currency = row.find_element(By.CLASS_NAME, "calendar__currency").text
                actual = row.find_element(By.CLASS_NAME, "calendar__actual").text
                forecast = row.find_element(By.CLASS_NAME, "calendar__forecast").text
                time_str = row.find_element(By.CLASS_NAME, "calendar__time").text
                
                # Check the colour of the icon to decide importance
                impact_element = row.find_element(By.CLASS_NAME, "calendar__impact").find_element(By.TAG_NAME, "span")
                impact_class = impact_element.get_attribute("class").lower()
                
                impact = "Low"
                if "high" in impact_class or "red" in impact_class:
                    impact = "High"
                elif "medium" in impact_class or "ora" in impact_class: # "ora" = orange
                    impact = "Medium"

                # Filter: We only want High and Medium impact news
                if impact in ["High", "Medium"]:
                    events.append({
                        "currency": currency,
                        "event": event_name,
                        "impact": impact,
                        "actual": actual,
                        "forecast": forecast,
                        "time": time_str
                    })
            except:
                # If a row is missing data (like a banner ad), skip it
                continue

    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        driver.quit()
        
    return events

# This only runs if you run this specific file directly
if __name__ == "__main__":
    print("Running scraper test...")
    data = get_forex_events()
    
    if not data:
        print("No High/Medium impact events found today.")
    else:
        print(f"Success! Found {len(data)} events:")
        for item in data:
            print(f"[{item['time']}] {item['currency']} - {item['event']} ({item['impact']})")