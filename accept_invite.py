import requests
import time
from bs4 import BeautifulSoup
import re
import sys
import urllib.parse
import base64
import json
from urllib.parse import urljoin, unquote, urlparse
from utils import load_config

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import platform
import os

# --- Configuration ---
EMAIL_SERVER = 'maildev'  # or 'gmail'
MAILDEV_URL = 'https://mail.localhost.dataplanes.pro'
USE_API_METHOD = True  # Set to True to use REST API instead of Selenium

# Disable warnings for local/self-signed certs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_chromedriver_path():
    """
    Get the correct ChromeDriver path, handling Linux issues where
    webdriver_manager might point to THIRD_PARTY_NOTICES instead of the executable.

    Returns:
        str: Path to the ChromeDriver executable
    """
    try:
        driver_path = ChromeDriverManager().install()

        # On Linux, webdriver_manager sometimes points to THIRD_PARTY_NOTICES file
        # instead of the actual chromedriver executable
        if platform.system() == "Linux":
            # Check if the path points to THIRD_PARTY_NOTICES or is not executable
            if "THIRD_PARTY_NOTICES" in driver_path or not os.access(driver_path, os.X_OK):
                print(f"[DEBUG] Incorrect ChromeDriver path detected: {driver_path}")
                print(f"[DEBUG] Searching for actual chromedriver executable...")

                # Get the directory where chromedriver should be
                driver_dir = os.path.dirname(driver_path)

                # Search for the actual chromedriver executable
                for root, dirs, files in os.walk(driver_dir):
                    for file in files:
                        if file == "chromedriver":
                            full_path = os.path.join(root, file)
                            # Verify it's executable
                            if os.access(full_path, os.X_OK):
                                print(f"[DEBUG] Found ChromeDriver executable: {full_path}")
                                return full_path

                print(f"[!] Could not find executable chromedriver in {driver_dir}")
                print(f"[!] Falling back to original path: {driver_path}")

        return driver_path

    except Exception as e:
        print(f"[!] Error finding ChromeDriver: {e}")
        raise

def accept_eula_fallback(redirect_url, session):
    """
    Fallback method using requests to accept EULA if Selenium fails.

    Args:
        redirect_url: The EULA acceptance URL
        session: requests.Session object with existing cookies

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"\n[*] Fallback: Accepting EULA via requests: {redirect_url}")
        eula_res = session.get(redirect_url, allow_redirects=True)

        print(f"[DEBUG] Response Status: {eula_res.status_code}")
        print(f"[DEBUG] Final URL: {eula_res.url}")

        if eula_res.status_code == 200:
            if 'login-saml' in eula_res.url or 'sso' in eula_res.url:
                print("[+] EULA acceptance redirected to SAML login - Success!")
                return True
            else:
                print("[+] EULA acceptance completed (requests fallback)")
                return True
        else:
            print(f"[!] EULA acceptance fallback failed with status: {eula_res.status_code}")
            return False

    except Exception as e:
        print(f"[!] EULA fallback error: {e}")
        return False

def decode_base64_if_needed(text):
    """
    Checks if a string is base64 encoded and decodes it.
    Handles missing padding which is common in URLs.
    """
    if '@' in text:
        return text
    try:
        # Add padding if missing
        missing_padding = len(text) % 4
        if missing_padding:
            text += '=' * (4 - missing_padding)
        decoded = base64.b64decode(text).decode('utf-8')
        if '@' in decoded:
            return decoded
    except Exception:
        pass
    return text

def extract_invite_details_from_page(session, invite_url):
    """Extract inviteId, userEntityId, accountId from invite page"""
    # print(f"[DEBUG] Fetching invite page to extract details...")

    try:
        response = session.get(invite_url, verify=False, allow_redirects=True)
        # print(f"[DEBUG] Page fetch status: {response.status_code}")

        invite_data = {}

        # Extract inviteId from URL
        invite_id_match = re.search(r'/invites/([a-z0-9]+)', invite_url)
        if invite_id_match:
            invite_data['inviteId'] = invite_id_match.group(1)
            # print(f"[DEBUG] Extracted inviteId: {invite_data['inviteId']}")

        # Parse page for other details
        soup = BeautifulSoup(response.text, 'html.parser')

        # Look in scripts
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                user_entity_match = re.search(r'userEntityId["\']?\s*[:=]\s*["\']([a-z0-9]+)["\']', script.string, re.IGNORECASE)
                if user_entity_match:
                    invite_data['userEntityId'] = user_entity_match.group(1)
                    # print(f"[DEBUG] Extracted userEntityId: {invite_data['userEntityId']}")

                account_id_match = re.search(r'accountId["\']?\s*[:=]\s*["\']([A-Z0-9]+)["\']', script.string, re.IGNORECASE)
                if account_id_match:
                    invite_data['accountId'] = account_id_match.group(1)
                    # print(f"[DEBUG] Extracted accountId: {invite_data['accountId']}")

        # Look in page source
        if 'userEntityId' not in invite_data:
            user_entity_match = re.search(r'"userEntityId":\s*"([a-z0-9]+)"', response.text)
            if user_entity_match:
                invite_data['userEntityId'] = user_entity_match.group(1)
                # print(f"[DEBUG] Found userEntityId in source: {invite_data['userEntityId']}")

        if 'accountId' not in invite_data:
            account_id_match = re.search(r'"accountId":\s*"([A-Z0-9]+)"', response.text)
            if account_id_match:
                invite_data['accountId'] = account_id_match.group(1)
                # print(f"[DEBUG] Found accountId in source: {invite_data['accountId']}")

        return invite_data

    except Exception as e:
        print(f"[!] Error extracting invite details: {e}")
        return {}

def accept_invitation_api(session, tenant_host, invite_id, user_details, invite_data):
    """Accept invitation via REST API PUT call"""
    print(f"[*] Accepting invitation via REST API...")

    api_url = f"{tenant_host}/cp/v1/accept-invitation/"

    payload = {
        "inviteId": invite_id,
        "eula": True,
        "userDetails": {
            "firstName": user_details.get('firstName', 'Automation'),
            "lastName": user_details.get('lastName', 'User'),
            "userEntityId": invite_data.get('userEntityId', ''),
            "accountId": invite_data.get('accountId', '')
        }
    }

    # print(f"[DEBUG] API URL: {api_url}")
    # print(f"[DEBUG] Payload: {json.dumps(payload, indent=2)}")

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'Origin': tenant_host,
        'Referer': f"{tenant_host}/cp/invites/{invite_id}"
    }

    if 'tsc' in session.cookies:
        headers['x-xsrf-token'] = session.cookies.get('tsc')

    try:
        response = session.put(api_url, json=payload, headers=headers, verify=False, timeout=30)

        # print(f"[DEBUG] Response Status: {response.status_code}")

        if response.status_code == 200:
            try:
                response_json = response.json()
                # print(f"[+] API Response: {json.dumps(response_json, indent=2)}")
                if 'Successfully accepted' in response_json.get('message', ''):
                    print(f"[+] Invitation accepted successfully via API!")
                    return True
            except:
                print(f"[+] Invitation accepted (status 200)")
                return True
        else:
            print(f"[!] API call failed with status: {response.status_code}")
            # print(f"[!] Response: {response.text[:300]}")
            return False

    except Exception as e:
        print(f"[!] Error during API call: {e}")
        return False

def reauthorize_session(session, tenant_host):
    """Call reauthorize endpoint to get final session cookies"""
    print(f"[*] Reauthorizing session...")

    reauth_url = f"{tenant_host}/idm/v1/reauthorize"
    payload = {
        'opaque-for-tenant': 'TSC',
        'resumeURL': f'{tenant_host}/cp/app/home'
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        response = session.post(reauth_url, data=payload, headers=headers, verify=False, allow_redirects=False, timeout=30)
        # print(f"[DEBUG] Reauthorize status: {response.status_code}")

        if 'tsc' in session.cookies and 'cic-user-at' in session.cookies:
            print(f"[+] Session cookies obtained successfully!")
            return True
        elif response.status_code in [200, 302, 303]:
            print(f"[+] Reauthorization successful!")
            return True
        else:
            print(f"[*] Reauthorization completed with status {response.status_code}")
            return True

    except Exception as e:
        print(f"[!] Error during reauthorization: {e}")
        return False

def accept_eula_api_method(redirect_url, user_details, session):
    """Accept EULA using REST API calls instead of Selenium"""
    print(f"\n{'='*60}")
    print("[*] Step 2: Accepting EULA via REST API")
    print(f"{'='*60}")
    # print(f"[DEBUG] Target URL: {redirect_url}")

    # Extract tenant host and invite ID
    parsed = urlparse(redirect_url)
    tenant_host = f"{parsed.scheme}://{parsed.netloc}"

    invite_id_match = re.search(r'/invites/([a-z0-9]+)', redirect_url)
    if not invite_id_match:
        print("[!] Could not extract invite ID from URL")
        return False

    invite_id = invite_id_match.group(1)
    # print(f"[DEBUG] Tenant Host: {tenant_host}")
    # print(f"[DEBUG] Invite ID: {invite_id}")

    # Step 1: Extract details from page
    invite_data = extract_invite_details_from_page(session, redirect_url)
    if not invite_data.get('inviteId'):
        invite_data['inviteId'] = invite_id

    # Step 2: Accept via API
    success = accept_invitation_api(session, tenant_host, invite_id, user_details, invite_data)
    if not success:
        print("[!] API acceptance failed, falling back to Selenium...")
        return False

    # Step 3: Reauthorize
    reauth_success = reauthorize_session(session, tenant_host)

    if reauth_success:
        print(f"\n{'='*60}")
        print("[+] EULA Acceptance Complete via API!")
        print(f"{'='*60}")
        return True
    else:
        print("[*] Invitation accepted, reauthorization may be pending")
        return True

def accept_eula_with_selenium(redirect_url, user_details):
    """
    Accept EULA using Selenium WebDriver for better handling of interactive elements.

    Args:
        redirect_url: The EULA acceptance URL from registration response
        user_details: User configuration details

    Returns:
        bool: True if EULA accepted successfully, False otherwise
    """
    driver = None
    try:
        print(f"\n[*] Step 2: Accepting EULA via Selenium")
        # print(f"[DEBUG] Target URL: {redirect_url}")

        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--allow-insecure-localhost')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-logging')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-cloud-management')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Initialize Chrome WebDriver with webdriver-manager
        # print("[DEBUG] Initializing Chrome WebDriver...")
        try:
            chromedriver_path = get_chromedriver_path()
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)
            # print("[DEBUG] Chrome WebDriver initialized successfully")
        except Exception as driver_error:
            print(f"[!] Failed to initialize Chrome WebDriver: {driver_error}")
            print("[*] Please ensure Google Chrome is installed")
            raise

        # Navigate to EULA page
        # print(f"[DEBUG] Navigating to: {redirect_url}")
        driver.get(redirect_url)

        # Wait for initial page load
        time.sleep(2)

        # Log current URL and title
        # print(f"[DEBUG] Current URL: {driver.current_url}")
        # print(f"[DEBUG] Page Title: {driver.title}")

        # Handle SSO flow if detected
        if '/sso' in driver.current_url or '/login' in driver.current_url:
            # print("[DEBUG] SSO authentication page detected, performing login...")

            # Check if we're on the SSO page that needs credentials
            try:
                # Wait for the SSO page to load completely
                time.sleep(2)

                # Check if there are username/password fields (SSO login form)
                username_field = None
                password_field = None

                # Try to find username field
                username_selectors = [
                    (By.ID, "username"),
                    (By.ID, "email"),
                    (By.NAME, "username"),
                    (By.NAME, "email"),
                    (By.XPATH, "//input[@type='text' or @type='email']")
                ]

                for by, selector in username_selectors:
                    try:
                        username_field = driver.find_element(by, selector)
                        # print(f"[DEBUG] Found username field using: {by}='{selector}'")
                        break
                    except NoSuchElementException:
                        continue

                # Try to find password field
                password_selectors = [
                    (By.ID, "password"),
                    (By.NAME, "password"),
                    (By.XPATH, "//input[@type='password']")
                ]

                for by, selector in password_selectors:
                    try:
                        password_field = driver.find_element(by, selector)
                        # print(f"[DEBUG] Found password field using: {by}='{selector}'")
                        break
                    except NoSuchElementException:
                        continue

                # If we found login fields, submit credentials
                if username_field and password_field:
                    # print("[DEBUG] Filling SSO login credentials...")

                    # IMPORTANT: Use the INVITED USER's credentials, not admin
                    # The invited user's email should be in user_details or extracted from the flow
                    config = load_config()

                    # Get invited user email from config (invite_user_email)
                    username = config.get('invite_user_email', '')

                    # If not in config, try to get from user_details
                    if not username and 'email' in user_details:
                        username = user_details.get('email')

                    # Get password from new_user_details (the invited user's password)
                    password = user_details.get('password') or config.get('new_user_details', {}).get('password', 'Tibco@2025')

                    # print(f"[DEBUG] Using invited user credentials for SSO login")

                    # Fill in credentials
                    username_field.clear()
                    username_field.send_keys(username)
                    # print(f"[DEBUG] Entered username: {username}")

                    password_field.clear()
                    password_field.send_keys(password)
                    # print("[DEBUG] Entered password")

                    # Find and click submit button
                    submit_button = None
                    submit_selectors = [
                        (By.ID, "submit"),
                        (By.ID, "login"),
                        (By.XPATH, "//button[@type='submit']"),
                        (By.XPATH, "//input[@type='submit']"),
                        (By.XPATH, "//button[contains(text(), 'Sign in') or contains(text(), 'Login')]")
                    ]

                    for by, selector in submit_selectors:
                        try:
                            submit_button = driver.find_element(by, selector)
                            # print(f"[DEBUG] Found submit button using: {by}='{selector}'")
                            break
                        except NoSuchElementException:
                            continue

                    if submit_button:
                        # print("[DEBUG] Clicking submit button...")
                        submit_button.click()
                        time.sleep(3)
                        # print(f"[DEBUG] After login - Current URL: {driver.current_url}")
                    else:
                        print("[!] Submit button not found, trying form submit...")
                        # Try to submit the form via JavaScript
                        driver.execute_script("document.forms[0].submit();")
                        time.sleep(3)
                else:
                    pass
                    # print("[DEBUG] No login fields found, page may be auto-authenticating...")

            except Exception as login_error:
                print(f"[!] Error during SSO login: {login_error}")

            # Wait for acscallback or cookie form after login
            max_wait = 30
            wait_interval = 2
            elapsed = 0

            while elapsed < max_wait:
                current_url = driver.current_url
                # print(f"[DEBUG] Waiting for SSO completion... Current: {current_url}")

                # Check if we've reached the invite page
                if '/invites/' in current_url and '/cp/' in current_url:
                    # print(f"[DEBUG] Reached invite page: {current_url}")
                    break

                # Check for acscallback page
                if '/acscallback' in current_url or '/idm/acscallback' in current_url:
                    # print(f"[DEBUG] Reached acscallback: {current_url}")
                    time.sleep(2)  # Wait for potential redirect
                    continue

                # Check for cookie form submission page
                page_source = driver.page_source
                if 'idm/v1/cookie' in page_source or "action='https://" in page_source:
                    # print("[DEBUG] Detected cookie form in page source, extracting location...")

                    # Look for the hidden form and extract location
                    try:
                        # Try to find the location input field
                        location_input = driver.find_element(By.NAME, "location")
                        final_url = location_input.get_attribute('value')
                        # print(f"[DEBUG] Extracted final location: {final_url}")

                        # The form should auto-submit via JavaScript, but let's ensure it
                        time.sleep(2)

                        # Check if still on same page, if so, manually submit
                        if driver.current_url == current_url:
                            # print("[DEBUG] Form did not auto-submit, submitting manually...")
                            try:
                                submit_btn = driver.find_element(By.ID, "submit")
                                driver.execute_script("arguments[0].click();", submit_btn)
                                # print("[DEBUG] Clicked submit button")
                            except NoSuchElementException:
                                # Try form submission
                                driver.execute_script("document.forms[0].submit();")
                                # print("[DEBUG] Submitted form via JavaScript")

                            time.sleep(3)

                        break
                    except NoSuchElementException:
                        pass
                        # print("[DEBUG] Location field not found yet, waiting...")

                time.sleep(wait_interval)
                elapsed += wait_interval

            # Final check after SSO flow
            time.sleep(2)
            # print(f"[DEBUG] Final URL after SSO: {driver.current_url}")
            # print(f"[DEBUG] Final Page Title: {driver.title}")

        # Now check if we're on a EULA acceptance page
        # Look for common EULA elements: checkbox, accept button, terms text
        try:
            # Strategy 1: Look for EULA checkbox
            # print("[DEBUG] Looking for EULA checkbox...")
            eula_checkbox = None

            # Try multiple selector strategies
            checkbox_selectors = [
                (By.ID, "eula-checkbox"),
                (By.ID, "accept-eula"),
                (By.NAME, "eula"),
                (By.XPATH, "//input[@type='checkbox' and contains(@id, 'eula')]"),
                (By.XPATH, "//input[@type='checkbox' and contains(@name, 'eula')]"),
                (By.CSS_SELECTOR, "input[type='checkbox'][id*='eula']"),
                (By.CSS_SELECTOR, ".pl-form-field--checkbox input[type='checkbox']"),
            ]

            for by, selector in checkbox_selectors:
                try:
                    eula_checkbox = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    # print(f"[DEBUG] Found EULA checkbox using: {by}='{selector}'")
                    break
                except TimeoutException:
                    continue

            if eula_checkbox:
                # Check if checkbox is already checked
                if not eula_checkbox.is_selected():
                    # print("[DEBUG] Clicking EULA checkbox...")
                    driver.execute_script("arguments[0].click();", eula_checkbox)
                    time.sleep(0.5)
                    print("[+] EULA checkbox checked")
                else:
                    pass
                    # print("[DEBUG] EULA checkbox already checked")
            else:
                pass
                # print("[DEBUG] No EULA checkbox found - may be auto-accepted")

            # Strategy 2: Look for Accept/Continue button
            # print("[DEBUG] Looking for Accept/Continue button...")
            accept_button = None

            button_selectors = [
                (By.ID, "accept-invitation-btn"),
                (By.ID, "accept-invite"),
                (By.XPATH, "//button[contains(text(), 'Accept')]"),
                (By.XPATH, "//button[contains(text(), 'Continue')]"),
                (By.XPATH, "//button[contains(@class, 'accept')]"),
                (By.CSS_SELECTOR, "button.pl-button--primary"),
                (By.CSS_SELECTOR, "button[type='submit']"),
            ]

            for by, selector in button_selectors:
                try:
                    accept_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    # print(f"[DEBUG] Found Accept button using: {by}='{selector}'")
                    break
                except TimeoutException:
                    continue

            if accept_button:
                # print("[DEBUG] Clicking Accept button...")
                driver.execute_script("arguments[0].click();", accept_button)
                print("[+] Accept button clicked")

                # Wait for API call to complete and redirect
                # print("[DEBUG] Waiting for invitation acceptance API call to complete...")
                time.sleep(3)

                # Wait for redirect to home page or reauthorize
                max_wait = 30
                wait_interval = 2
                elapsed = 0
                redirect_detected = False

                while elapsed < max_wait:
                    current_url = driver.current_url
                    page_title = driver.title

                    # Check if redirected to home page (success)
                    if '/app/home' in current_url or '/cp/app/home' in current_url:
                        # print(f"[DEBUG] ✓ Redirected to home page: {current_url}")
                        redirect_detected = True
                        break

                    # Check if URL changed from invite page
                    if '/invites/' not in current_url:
                        # print(f"[DEBUG] URL changed to: {current_url}")
                        redirect_detected = True
                        time.sleep(2)  # Wait a bit more for final redirect
                        break

                    # Check if page content changed (invitation accepted)
                    if 'successfully accepted' in driver.page_source.lower() or 'welcome' in page_title.lower():
                        # print(f"[DEBUG] ✓ Success message detected in page")
                        redirect_detected = True
                        time.sleep(2)
                        break

                    # print(f"[DEBUG] Waiting for redirect... ({elapsed}s) Current: {current_url}")
                    time.sleep(wait_interval)
                    elapsed += wait_interval

                if redirect_detected:
                    print("[+] Invitation acceptance completed successfully!")
                else:
                    print("[!] No redirect detected after clicking Accept, but button was clicked")
                    print("[*] Acceptance may still have succeeded via background API call")

            else:
                pass
                # print("[DEBUG] No Accept button found - checking if auto-redirected")


            # Log final URL after acceptance
            final_url = driver.current_url
            # print(f"\n{'='*60}")
            # print(f"[DEBUG] EULA Acceptance via Selenium - Results")
            # print(f"{'='*60}")
            # print(f"[DEBUG] Initial URL: {redirect_url}")
            # print(f"[DEBUG] Final URL: {final_url}")
            # print(f"[DEBUG] Page Title: {driver.title}")

            # Check if we've been redirected to home or success page
            if '/app/home' in final_url or '/cp/app/home' in final_url:
                # print(f"[DEBUG] ✓ Successfully redirected to home page!")
                print(f"[+] EULA accepted successfully and user logged in!")
                return True
            elif 'login-saml' in final_url or 'sso' in final_url or 'idm' in final_url:
                # print(f"[DEBUG] ✓ SAML Login Flow Detected!")
                # print(f"[DEBUG] ✓ EULA acceptance triggered automatic authentication")
                print(f"[+] EULA accepted successfully!")
                return True
            elif '/invites/' not in final_url:
                # print(f"[DEBUG] ✓ Redirected away from invite page")
                print(f"[+] EULA acceptance appears successful!")
                return True
            else:
                print(f"[!] Still on invite page after acceptance attempt")
                print(f"[*] Checking page content for success indicators...")

                # Check page source for success indicators
                page_source = driver.page_source.lower()
                if 'successfully' in page_source or 'welcome' in page_source or 'accepted' in page_source:
                    print(f"[+] Success indicator found in page content!")
                    return True
                else:
                    print(f"[!] No clear success indicator found")
                    return False

            # Check cookies
            cookies = driver.get_cookies()
            # if cookies:
            #     print(f"\n[DEBUG] Cookies Set ({len(cookies)}):")
            #     for cookie in cookies[:5]:  # Show first 5 cookies
            #         print(f"    {cookie['name']}: {cookie['value'][:30]}...")

            # print(f"{'='*60}\n")

            # Determine success based on URL change or cookies
            success = (final_url != redirect_url) or len(cookies) > 0

            if success:
                print("[+] EULA acceptance flow completed successfully!")
                print("[*] User account is fully activated and ready to login")
                return True
            else:
                print("[!] EULA acceptance may have failed - no URL change detected")
                return False

        except Exception as inner_e:
            print(f"[!] Error during EULA interaction: {inner_e}")
            # print(f"[DEBUG] Current URL: {driver.current_url}")

            # Take screenshot for debugging
            try:
                screenshot_path = f"eula_error_{int(time.time())}.png"
                driver.save_screenshot(screenshot_path)
                # print(f"[DEBUG] Screenshot saved to: {screenshot_path}")
            except:
                pass

            return False

    except Exception as e:
        print(f"[!] Selenium error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Clean up - close browser
        if driver:
            try:
                # print("[DEBUG] Closing WebDriver...")
                driver.quit()
            except:
                pass

def read_email_maildev(link_pattern, email_address):
    import email.utils
    for _ in range(10):
        try:
            response = requests.get(f'{MAILDEV_URL}/email', verify=False)
            response.raise_for_status()
            emails = response.json()
            filtered = [e for e in emails if not e.get('read') and any(t['address'] == email_address for t in e.get('to', []))]
            
            if filtered:
                email_obj = filtered[0]
                email_body = email_obj.get('html') or email_obj.get('text', '')
                requests.patch(f'{MAILDEV_URL}/email/read-all', verify=False)
                match = re.search(r'<a[^>]+href=["\']([^"\']*' + link_pattern + r'[^"\']*)["\']', email_body)
                return match.group(1) if match else None
        except Exception as e:
            print(f"[!] Error checking MailDev: {e}")
        time.sleep(5)
    return None

def submit_registration(invite_url, user_details):
    """
    Visits the invite link and performs the Reset Password API call 
    as specified in the successful curl command.
    """
    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.5',
    })

    print(f"[*] Step 1: Visiting invite link: {invite_url}")
    res = session.get(invite_url, allow_redirects=True)
    
    # --- Handle Reset Password Flow ---
    if "/admin/reset-password/" in res.url:
        print(f"[*] Detected Reset Password Flow: {res.url}")
        
        try:
            # The URL ends with TOKEN|EMAIL|SOURCE
            decoded_url = unquote(res.url)
            # Find the segment after 'reset-password/'
            match = re.search(r'/reset-password/([^|/]+)\|([^|/]+)', decoded_url)
            
            if match:
                token = match.group(1)
                email_raw = match.group(2)
                email = decode_base64_if_needed(email_raw)
            else:
                # Fallback for alternative encoding or format
                token_segment = decoded_url.split('/')[-1]
                segments = token_segment.split('|')
                if len(segments) >= 2:
                    token = segments[0]
                    email = decode_base64_if_needed(segments[1])
                else:
                    raise ValueError("Could not parse token/email from URL")

            print(f"[*] Extracted Token: {token[:10]}...")
            print(f"[*] Decoded Email: {email}")

            idp_host = user_details.get('idp_host', 'https://admin.cp1-my.localhost.dataplanes.pro')
            reset_api_url = f"{idp_host}/idp/v1/reset-password"
            
            # Payload strictly matching the successful curl requirement
            payload = {
                'firstName': user_details.get('firstName', 'Kishor'),
                'lastName': user_details.get('lastName', 'Patil'),
                'userPasswordToken': token,
                'email': email,
                'password': user_details.get('password', 'Tibco@2025')
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': res.url,
                'Origin': idp_host,
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin'
            }
            
            # ====== DEBUG: REQUEST DETAILS ======
            # print(f"\n{'='*60}")
            # print(f"[DEBUG] Registration (Reset Password) Request Details")
            # print(f"{'='*60}")
            # print(f"[DEBUG] Target URL: {reset_api_url}")
            # print(f"[DEBUG] Request Method: POST")
            # print(f"[DEBUG] Content-Type: application/x-www-form-urlencoded")
            # print(f"\n[DEBUG] Request Payload:")
            # # Mask password for security but show other fields
            # debug_payload = payload.copy()
            # debug_payload['password'] = '***MASKED***'
            # debug_payload['userPasswordToken'] = token[:15] + '...' if len(token) > 15 else token
            # for key, value in debug_payload.items():
            #     print(f"        {key}: {value}")
            # print(f"\n[DEBUG] Request Headers:")
            # for key, value in headers.items():
            #     print(f"        {key}: {value}")
            # print(f"{'='*60}\n")
            # ====================================

            print(f"[*] Posting Registration Data to: {reset_api_url}")
            reg_res = session.post(reset_api_url, data=payload, headers=headers, allow_redirects=True)
            
            # ====== DEBUG: RESPONSE DETAILS ======
            # print(f"\n{'='*60}")
            # print(f"[DEBUG] Registration (Reset Password) Response Details")
            # print(f"{'='*60}")
            # print(f"[DEBUG] Response Status Code: {reg_res.status_code}")
            # print(f"[DEBUG] Response URL: {reg_res.url}")
            # print(f"[DEBUG] Redirect History: {len(reg_res.history)} redirect(s)")
            # if reg_res.history:
            #     for idx, hist_resp in enumerate(reg_res.history):
            #         print(f"        Redirect {idx+1}: {hist_resp.status_code} -> {hist_resp.url}")

            # print(f"\n[DEBUG] Response Headers:")
            # for header, value in reg_res.headers.items():
            #     print(f"        {header}: {value}")

            # print(f"\n[DEBUG] Response Cookies:")
            # if reg_res.cookies:
            #     for cookie in reg_res.cookies:
            #         print(f"        {cookie.name}: {cookie.value[:20]}..." if len(cookie.value) > 20 else f"        {cookie.name}: {cookie.value}")
            # else:
            #     print(f"        (No cookies set)")

            # print(f"\n[DEBUG] Raw Response Body:")
            # if reg_res.text:
            #     # Try to pretty print if JSON
            #     # try:
            #     #     import json
            #     #     response_json = reg_res.json()
            #     #     print(json.dumps(response_json, indent=4))
            #     # except:
            #     #     # Not JSON, show raw text (truncated if too long)
            #     #     if len(reg_res.text) > 500:
            #     #         print(f"        {reg_res.text[:500]}...")
            #     #         print(f"        ... (truncated, total length: {len(reg_res.text)} chars)")
            #     #     else:
            #     #         print(f"        {reg_res.text}")
            #     pass
            # else:
            #     print(f"        (Empty response body)")
            # print(f"{'='*60}\n")
            # ====================================

            if reg_res.status_code in [200, 201, 204]:
                print("[+] Registration (Reset Password) Successful!")

                # Step: Accept EULA - Check if we have a redirectUrl
                try:
                    response_data = reg_res.json()
                    if 'redirectUrl' in response_data:
                        redirect_url = response_data['redirectUrl']

                        # Try API method first (faster and more reliable)
                        if USE_API_METHOD:
                            print("[*] Attempting EULA acceptance via REST API...")
                            eula_accepted = accept_eula_api_method(redirect_url, user_details, session)

                            if eula_accepted:
                                print("[+] EULA acceptance completed via API!")
                                return True
                            else:
                                print("[!] API method failed, falling back to Selenium...")

                        # Fallback to Selenium for EULA acceptance
                        eula_accepted = accept_eula_with_selenium(redirect_url, user_details)

                        if eula_accepted:
                            print("[+] EULA acceptance completed via Selenium")
                            return True
                        else:
                            print("[!] EULA acceptance via Selenium failed, trying requests fallback...")
                            # Final fallback to requests-based approach
                            return accept_eula_fallback(redirect_url, session)
                    else:
                        print("[*] No EULA redirect found in response")
                        return True

                except Exception as e:
                    print(f"[*] Error processing EULA: {e}")
                    import traceback
                    traceback.print_exc()
                    return True  # Continue anyway as registration was successful

            else:
                print(f"[!] API call failed with status: {reg_res.status_code}")
                print(f"[*] Server Response: {reg_res.text[:300]}")
                return False

        except Exception as e:
            print(f"[!] Error during token extraction or API call: {e}")
            return False

    # --- Fallback: Standard Form Submission ---
    soup = BeautifulSoup(res.text, 'html.parser')
    form = soup.find('form')
    if form:
        action = urljoin(res.url, form.get('action', ''))
        payload = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
        payload.update({
            'firstName': user_details.get('firstName', 'Kishor'),
            'lastName': user_details.get('lastName', 'Patil'),
            'password': user_details.get('password', 'Tibco@2025')
        })
        reg_res = session.post(action, data=payload, allow_redirects=True)
        return reg_res.status_code == 200
    
    print(f"[!] No valid registration pattern found. URL: {res.url}")
    return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(1)
        
    target_email = sys.argv[1]
    
    # Load configuration
    config = load_config()
    new_user = config.get('new_user_details', {})
    
    # Priority for details from config.json
    details = {
        'email': target_email,  # Add the invited user's email
        'firstName': new_user.get('firstName', 'Kishor'),
        'lastName': new_user.get('lastName', 'Patil'),
        'password': new_user.get('password', 'Tibco@2025'),
        'idp_host': config.get('idp_host', 'https://admin.cp1-my.localhost.dataplanes.pro')
    }
    
    link = read_email_maildev('accept-invites', target_email)
    
    if link:
        print(f"[+] Found invite link in email.")
        success = submit_registration(link, details)
        sys.exit(0) if success else sys.exit(1)
    else:
        print(f"[!] No unread invite found for {target_email}.")
        sys.exit(1)