# ----------------- NOTES ------------------
# This script:
# 1) Starts a local Flask server to show a webpage where you can start the process.
# 2) Once you start the process, it launches a browser and navigates to the Threads.net login page.
# 3) YOU must log in manually in the opened browser window.
#    - If 2FA is enabled, complete it manually.
# 4) Once you're logged in (detected by URL change), the script navigates to the follower requests page.
# 5) The script attempts to accept a specified number of follower requests by clicking "Confirm" buttons.
#
# If you receive "No module named X" errors, install the package:
# e.g. "pip install selenium" for selenium, "pip install flask" for flask, etc.
#
# This is for demonstration/educational purposes. Use at your own risk.
#
# ------------------------------------------

import time
import random
import logging
import sys
import io
import webbrowser
from threading import Thread

from flask import Flask, render_template_string, request, redirect, url_for  # pip install flask

from selenium import webdriver  # pip install selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager  # pip install webdriver-manager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ----------------- CONFIGURATION ------------------

# Base URLs
LOGIN_URL = "https://www.threads.net/login/"
MAIN_URL = "https://www.threads.net/"
FOLLOW_REQUESTS_URL = "https://www.threads.net/activity/requests"

# Default settings
DEFAULT_MAX_REQUESTS = 1
DEFAULT_DELAY_MIN = 2
DEFAULT_DELAY_MAX = 6

# Selenium WebDriver wait time
EXPLICIT_WAIT = 90  # seconds

# ---------------------------------------------------

app = Flask(__name__)

# In-memory log capture for displaying logs in the web interface
log_capture = io.StringIO()

# Configure logging to write to our in-memory buffer
logging.basicConfig(
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(log_capture)]
)

# ----------------- HTML TEMPLATE ------------------
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <title>Threads Follower Requests Acceptance</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }
        .container { max-width: 700px; margin: auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); }
        h1, h2, h3 { text-align: center; color: #333; }
        form { display: flex; flex-direction: column; gap: 15px; }
        label { font-weight: bold; color: #555; }
        input[type="number"] {
            padding: 10px; 
            border: 1px solid #ccc; 
            border-radius: 4px;
            font-size: 16px;
        }
        button {
            padding: 12px; 
            background-color: #007bff;
            border: none; 
            border-radius: 4px;
            color: #fff; 
            font-size: 16px; 
            cursor: pointer;
            transition: background-color 0.3s ease;
        }
        button:hover { background-color: #0056b3; }
        .disclaimer {
            background: #fff3cd; 
            padding: 15px; 
            border-radius: 4px;
            color: #856404;
            margin-bottom: 25px;
            border: 1px solid #ffeeba;
        }
        pre { background: #f8f9fa; padding: 15px; border-radius: 4px; overflow: auto; max-height: 400px; }
        .logs-container { margin-top: 20px; }
        .footer { text-align: center; margin-top: 30px; color: #888; font-size: 14px; }
        a { color: #007bff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
<div class="container">
    <h1>Threads Follower Requests Acceptance</h1>
    <div class="disclaimer">
        <strong>Disclaimer:</strong> This script may violate Threads' Terms of Service. Use it at your own risk.
    </div>
    {% if not running and not completed %}
    <!-- Input form for max requests and delay times -->
    <h2>Set Your Parameters</h2>
    <p>When you start the process, a browser will open and take you to the Threads.net login page. Please log in manually.</p>
    <form method="POST" action="{{ url_for('run_script_route') }}">
        <label for="max_requests">Max Requests to Accept (Default: {{default_max}}):</label>
        <input type="number" name="max_requests" value="{{default_max}}" min="1" required>

        <label for="delay_min">Minimum Delay Time in Seconds (Default: {{default_delay_min}}):</label>
        <input type="number" name="delay_min" value="{{default_delay_min}}" min="1" required>

        <label for="delay_max">Maximum Delay Time in Seconds (Default: {{default_delay_max}}):</label>
        <input type="number" name="delay_max" value="{{default_delay_max}}" min="1" required>

        <button type="submit">Start Process</button>
    </form>
    {% elif running %}
    <h2>Process is Running...</h2>
    <p>Please log in to Threads.net in the opened browser if you haven't already. Complete any 2FA steps if prompted. Once logged in, the script will proceed automatically.</p>
    <div class="logs-container">
        <form action="{{ url_for('show_logs') }}">
            <button type="submit">Refresh Logs</button>
        </form>
        <pre>{{logs}}</pre>
    </div>
    {% elif completed %}
    <h2>Process Completed!</h2>
    <p>Below are the logs:</p>
    <div class="logs-container">
        <pre>{{logs}}</pre>
    </div>
    <a href="{{url_for('home')}}">Back to Home</a>
    {% endif %}
</div>
<div class="footer">
    Version: 0.03
</div>
</body>
</html>
"""

# Global state variables indicating process status
process_running = False
process_completed = False

# ----------------- HELPER FUNCTIONS ------------------

def human_delay(min_delay, max_delay):
    """
    Introduce a random human-like delay between actions to reduce suspicion.
    Adjust min_delay and max_delay as needed.
    """
    delay = random.uniform(min_delay, max_delay)
    logging.info(f"Sleeping for {delay:.2f} seconds to mimic human behavior.")
    time.sleep(delay)

def wait_for_manual_login(driver):
    """
    Wait for the user to manually log in.
    We'll continually check the current URL until it matches MAIN_URL.
    This includes handling 2FA.
    """
    logging.info("Waiting for manual login... Please complete the login in the opened browser window.")
    try:
        WebDriverWait(driver, EXPLICIT_WAIT).until(EC.url_to_be(MAIN_URL))
        logging.info("Detected successful login to Threads.net.")
    except TimeoutException:
        logging.warning("Timeout while waiting for login. Ensure you've completed the login process.")
        raise

def navigate_to_requests(driver, min_delay, max_delay):
    """
    Navigate to the Threads.net follower requests section.
    """
    logging.info(f"Navigating to follower requests page: {FOLLOW_REQUESTS_URL}")
    driver.get(FOLLOW_REQUESTS_URL)
    try:
        WebDriverWait(driver, EXPLICIT_WAIT).until(EC.url_to_be(FOLLOW_REQUESTS_URL))
        logging.info("Successfully navigated to follower requests page.")
    except TimeoutException:
        logging.warning("Timeout while navigating to follower requests page.")
        raise
    human_delay(min_delay, max_delay)

def accept_follower_requests(driver, max_requests, min_delay, max_delay):
    """
    Accept up to 'max_requests' follower requests by clicking "Confirm" buttons.
    """
    accepted_count = 0
    logging.info(f"Attempting to accept up to {max_requests} follower requests...")
    
    while accepted_count < max_requests:
        try:
            # Locate all "Confirm" buttons by their text content
            # Using XPath to find div elements with exact text "Confirm"
            confirm_buttons = driver.find_elements(By.XPATH, "//div[normalize-space(text())='Confirm']")
            
            if not confirm_buttons:
                logging.info("No 'Confirm' buttons found. Possibly no more follower requests or page structure has changed.")
                break

            for btn in confirm_buttons:
                if accepted_count >= max_requests:
                    break
                try:
                    # Scroll the button into view
                    driver.execute_script("arguments[0].scrollIntoView(true);", btn)
                    human_delay(min_delay, max_delay)
                    
                    # Click the "Confirm" button
                    btn.click()
                    accepted_count += 1
                    logging.info(f"Accepted follower request #{accepted_count}")
                    human_delay(min_delay, max_delay)
                except ElementClickInterceptedException:
                    logging.warning("Could not click the 'Confirm' button due to interception. Retrying...")
                    human_delay(min_delay, max_delay)
                except Exception as e:
                    logging.warning(f"Failed to click 'Confirm' button: {e}")
                    human_delay(min_delay, max_delay)

            # Optionally, refresh the list of buttons after some acceptances
            if accepted_count < max_requests:
                logging.info("Refreshing the follower requests list to find more 'Confirm' buttons.")
                driver.refresh()
                human_delay(min_delay, max_delay)

        except NoSuchElementException:
            logging.info("No 'Confirm' buttons found on the page.")
            break
        except TimeoutException:
            logging.warning("Timeout while loading follower requests. Retrying...")
            human_delay(min_delay, max_delay)
        except Exception as e:
            logging.error(f"An unexpected error occurred while accepting requests: {e}")
            break

    logging.info(f"Completed accepting follower requests. Total accepted: {accepted_count}")
    return accepted_count

def run_script(max_requests, delay_min, delay_max):
    """
    Main automation routine:
    1. Opens browser and navigates to Threads.net login page.
    2. Waits for you to manually log in (handles 2FA).
    3. Navigates to follower requests page on Threads.net.
    4. Accepts follower requests.
    """
    global process_running, process_completed

    # Clear the log buffer for a fresh start
    log_capture.seek(0)
    log_capture.truncate()

    logging.info("Starting the automation process... Opening browser...")

    # Log the configured delay times
    logging.info(f"Configured Delay Times - Min: {delay_min} seconds, Max: {delay_max} seconds")

    # Configure Chrome options
    options = webdriver.ChromeOptions()
    # Uncomment the following line to run Chrome in headless mode
    # options.add_argument('--headless')

    # Recommended arguments to reduce noise and overhead
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--start-maximized')  # Start maximized for better element visibility

    # Initialize the Chrome driver
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    try:
        # Step 1: Navigate to Threads.net login page
        logging.info(f"Navigating to Threads.net login page: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        human_delay(delay_min, delay_max)

        # Step 2: Wait for manual login (handles 2FA)
        wait_for_manual_login(driver)

        # Step 3: Navigate to follower requests page
        navigate_to_requests(driver, delay_min, delay_max)

        # Step 4: Accept follower requests
        accept_follower_requests(driver, max_requests, delay_min, delay_max)

    except Exception as e:
        logging.error(f"An unexpected error occurred during the automation process: {e}")
    finally:
        driver.quit()
        logging.info("Browser closed. Automation process finished.")
        process_running = False
        process_completed = True

# ----------------- FLASK ROUTES ------------------

@app.route('/', methods=['GET'])
def home():
    global process_running, process_completed
    logs = ""
    return render_template_string(
        HTML_TEMPLATE,
        running=process_running,
        completed=process_completed,
        default_max=DEFAULT_MAX_REQUESTS,
        default_delay_min=DEFAULT_DELAY_MIN,
        default_delay_max=DEFAULT_DELAY_MAX,
        logs=logs
    )

@app.route('/run', methods=['POST'])
def run_script_route():
    global process_running, process_completed

    if process_running:
        logging.info("Process is already running. Please wait until it completes.")
        return redirect(url_for('home'))

    # Capture form inputs
    max_requests = request.form.get('max_requests', '').strip()
    delay_min = request.form.get('delay_min', '').strip()
    delay_max = request.form.get('delay_max', '').strip()

    # Validate and set max_requests
    if not max_requests.isdigit() or int(max_requests) < 1:
        max_requests = DEFAULT_MAX_REQUESTS
        logging.info(f"Invalid input for max_requests. Using default value: {DEFAULT_MAX_REQUESTS}")
    else:
        max_requests = int(max_requests)
        logging.info(f"Max requests to accept set to: {max_requests}")

    # Validate and set delay_min
    if not delay_min.isdigit() or int(delay_min) < 1:
        delay_min = DEFAULT_DELAY_MIN
        logging.info(f"Invalid input for delay_min. Using default value: {DEFAULT_DELAY_MIN}")
    else:
        delay_min = int(delay_min)
        logging.info(f"Minimum delay time set to: {delay_min} seconds")

    # Validate and set delay_max
    if not delay_max.isdigit() or int(delay_max) < 1:
        delay_max = DEFAULT_DELAY_MAX
        logging.info(f"Invalid input for delay_max. Using default value: {DEFAULT_DELAY_MAX}")
    else:
        delay_max = int(delay_max)
        logging.info(f"Maximum delay time set to: {delay_max} seconds")

    # Ensure that delay_min is not greater than delay_max
    if delay_min > delay_max:
        logging.warning(f"Minimum delay ({delay_min}) is greater than maximum delay ({delay_max}). Swapping values.")
        delay_min, delay_max = delay_max, delay_min

    # Run the script in a separate thread so the UI remains responsive
    def run_in_thread():
        global process_running, process_completed
        process_running = True
        process_completed = False
        run_script(max_requests, delay_min, delay_max)

    t = Thread(target=run_in_thread)
    t.start()

    return redirect(url_for('home'))

@app.route('/logs', methods=['GET'])
def show_logs():
    global process_running, process_completed
    log_capture.seek(0)
    logs = log_capture.read()
    return render_template_string(
        HTML_TEMPLATE,
        running=process_running,
        completed=process_completed,
        default_max=DEFAULT_MAX_REQUESTS,
        default_delay_min=DEFAULT_DELAY_MIN,
        default_delay_max=DEFAULT_DELAY_MAX,
        logs=logs
    )

# ----------------- BROWSER OPENING ------------------

def open_browser():
    """
    Automatically open the web browser to the Flask app.
    This is optional and can be removed if not desired.
    """
    time.sleep(2)  # Wait a moment for the server to start
    webbrowser.open_new("http://127.0.0.1:5000")

# ----------------- MAIN ENTRY POINT ------------------
if __name__ == "__main__":
    # Start a thread to open the browser after the server starts
    browser_thread = Thread(target=open_browser)
    browser_thread.start()

    # Run the Flask app
    app.run(debug=False)
