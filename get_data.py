import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

def get_forex_events():
    # --- 1. SETUP ---
    chrome_options = Options()
    
    # CRITICAL: Always run headless on servers
    chrome_options.add_argument("--headless") 
    
    # Standard server arguments
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Fake user agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    # --- SMART DRIVER SELECTION ---
    # This block detects if we are on PythonAnywhere or Local Laptop
    try:
        if "PYTHONANYWHERE_DOMAIN" in os.environ:
            # We are on the Server! Use their pre-installed Chrome.
            print("Detecting PythonAnywhere environment...")
            chrome_options.binary_location = "/usr/bin/chromium-browser"
            service = Service("/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # We are on the Laptop! Use the automatic manager.
            print("Running locally...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
    except Exception as e:
        print(f"Failed to initialize Chrome Driver: {e}")
        return []

    events = []
    
    try:
        # --- 2. FETCH PAGE ---
        print("Accessing ForexFactory...")
        driver.get("https://www.forexfactory.com/calendar?day=today")
        time.sleep(3) # Wait for page to load

        # --- 3. EXTRACT DATA ---
        rows = driver.find_elements(By.XPATH, "//tr[contains(@class, 'calendar__row')]")
        
        for row in rows:
            try:
                # Get Event Name
                event_name = row.find_element(By.CLASS_NAME, "calendar__event-title").text
                if not event_name: 
                    continue

                # Get basic info
                currency = row.find_element(By.CLASS_NAME, "calendar__currency").text
                actual = row.find_element(By.CLASS_NAME, "calendar__actual").text
                forecast = row.find_element(By.CLASS_NAME, "calendar__forecast").text
                time_str = row.find_element(By.CLASS_NAME, "calendar__time").text
                
                # Check impact color
                impact_element = row.find_element(By.CLASS_NAME, "calendar__impact").find_element(By.TAG_NAME, "span")
                impact_class = impact_element.get_attribute("class").lower()
                
                impact = "Low"
                if "high" in impact_class or "red" in impact_class:
                    impact = "High"
                elif "medium" in impact_class or "ora" in impact_class:
                    impact = "Medium"

                # Filter: High and Medium only
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
                continue

    except Exception as e:
        print(f"Error occurred during scraping: {e}")
    finally:
        # Always close the browser to save memory
        driver.quit()
        
    return events

# Test block
if __name__ == "__main__":
    print("Running scraper test...")
    data = get_forex_events()
    
    if not data:
        print("No High/Medium impact events found today.")
    else:
        print(f"Success! Found {len(data)} events:")
        for item in data:
            print(f"[{item['time']}] {item['currency']} - {item['event']} ({item['impact']})")