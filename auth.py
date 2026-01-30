import requests
import ssl
import urllib3
import urllib.parse
import re
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# Disable InsecureRequestWarning for custom/self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TLSAdapter(HTTPAdapter):
    """Adapter to force specific TLS versions if needed."""
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_version=ssl.PROTOCOL_TLSv1_2)

class SAMLAuthenticator:
    def __init__(self, host_idm, username, password):
        self.host_idm = host_idm
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = False
        self.session.trust_env = False 
        self.session.mount('https://', TLSAdapter())

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def extract_form_data(self, response):
        """Extracts form action and all input fields from a response."""
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form')
        if not form:
            return None, {}
        
        action = form.get('action')
        if action:
            action = urllib.parse.urljoin(response.url, action)
            
        inputs = {inp.get('name'): inp.get('value', '') for inp in form.find_all('input') if inp.get('name')}
        return action, inputs

    def get_dynamic_relay_state(self, path="/admin/login"):
        """Attempts to fetch a fresh RelayState from the login landing page."""
        landing_url = f"{self.host_idm}{path}"
        try:
            resp = self.session.get(landing_url, timeout=30, allow_redirects=True)
            parsed_url = urllib.parse.urlparse(resp.url)
            params = urllib.parse.parse_qs(parsed_url.query)
            
            if 'relayState' in params:
                return params['relayState'][0]
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            for link in soup.find_all(['a', 'form', 'input'], recursive=True):
                href = link.get('href') or link.get('action') or link.get('value')
                if href and 'relayState=' in href:
                    query = urllib.parse.urlparse(href).query or href
                    state = urllib.parse.parse_qs(query).get('relayState', [None])[0]
                    if state: return state
            
            if path == "/admin/login":
                return self.get_dynamic_relay_state(path="/cp/login")

        except Exception as e:
            print(f"[!] Warning: Could not fetch dynamic RelayState: {e}")
        return None

    def run_login_flow(self, relay_state_raw=None):
        if not relay_state_raw:
            relay_state_raw = self.get_dynamic_relay_state()
            
        if not relay_state_raw:
            print("[!] No RelayState found. Skipping flow.")
            return False

        # Step 1: Initiating SAML login flow
        login_url = f"{self.host_idm}/idm/v1/login-saml"
        step1_headers = {'Referer': f"{self.host_idm}/admin/login?relayState={urllib.parse.quote(relay_state_raw)}"}
        
        try:
            # print(f"[*] Sending Step 1 to {login_url}")
            resp1 = self.session.get(login_url, params={'relayState': relay_state_raw}, headers=step1_headers, timeout=30)
            # print(f"[*] Step 1 Status: {resp1.status_code}")
        except Exception as e:
            print(f"[!] Critical Error: Connection failed: {e}")
            return False

        idp_sso_url, saml_req_data = self.extract_form_data(resp1)
        if not idp_sso_url: 
            print("[!] Step 1 failed to extract IDP URL. Check if you are reachable.")
            return False

        # Step 2: Submit SAML Request to IDP
        # print(f"[*] Step 2: Posting SAMLRequest to {idp_sso_url}")
        resp2 = self.session.post(idp_sso_url, data=saml_req_data)
        
        # Step 3: IDP Login Page
        login_url, login_payload = self.extract_form_data(resp2)
        if not login_url:
            if 'SAMLResponse' in resp2.text:
                # print("[*] Already authenticated. Moving to Step 4.")
                resp3 = resp2
            else:
                print("[!] Step 3 failed: No login form found on IDP page.")
                return False
        else:
            # print(f"[*] Step 3: Entering credentials at {login_url}")
            user_field = next((k for k in login_payload.keys() if re.search(r'user|email|login', k, re.I)), 'username')
            pass_field = next((k for k in login_payload.keys() if re.search(r'pass|pwd', k, re.I)), 'password')
            login_payload[user_field] = self.username
            login_payload[pass_field] = self.password
            resp3 = self.session.post(login_url, data=login_payload)
            # print(f"[*] Step 3 Status: {resp3.status_code}")

        # Step 4: Extract SAMLResponse
        acs_url, saml_resp_data = self.extract_form_data(resp3)
        if not acs_url or 'SAMLResponse' not in saml_resp_data:
            print("[!] Step 4: IDP did not return a SAMLResponse.")
            return False

        # print(f"[*] Step 4: Posting SAMLResponse to {acs_url}")
        resp4 = self.session.post(acs_url, data=saml_resp_data, allow_redirects=True)
        
        # Step 5: Finalize session
        # print(f"[*] Step 5: Finalizing session (Final URL: {resp4.url})")

        # Check for error URLs
        if '/error/' in resp4.url or '/tsc/error/' in resp4.url:
            error_code = urllib.parse.parse_qs(urllib.parse.urlparse(resp4.url).query).get('code', ['Unknown'])[0]
            print(f"[!] Authentication error detected: {error_code}")
            print(f"[!] Error URL: {resp4.url}")
            if resp4.text:
                print(f"[!] Response preview: {resp4.text[:300]}")
            return False

        token = urllib.parse.parse_qs(urllib.parse.urlparse(resp4.url).query).get('token', [None])[0]
        
        if not token:
            _, final_form = self.extract_form_data(resp4)
            token = final_form.get('token')

        if token:
            print("[+] Token found. Establishing session cookie...")
            cookie_url = f"{self.host_idm}/idm/v1/cookie"
            self.session.post(cookie_url, data={'token': token, 'location': f"{self.host_idm}/cp/app/home"})
            return True
        
        if self.session.cookies.get('tsc'):
            print("[+] Token not in URL, but 'tsc' session cookie is present. Assuming success.")
            return True
        
        print("[!] Final Step: Token extraction failed.")
        return False

    def logout(self, path="/idm/logout-request"):
        """Logs out from the current IDM session."""
        logout_url = f"{self.host_idm}{path}"
        # print(f"[*] Attempting logout from {logout_url}...")

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': f"{self.host_idm}/admin/app/subscriptions/details",
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        data = {'resumeURL': '/'}
        
        try:
            resp = self.session.post(logout_url, headers=headers, data=data, timeout=30)

            # Clear all session cookies after logout
            self.session.cookies.clear()

            # A successful logout often redirects or returns a 200 on a landing page
            if resp.status_code == 200 or any(hist.status_code in [301, 302] for hist in resp.history):
                # print("[+] Admin logout successful.")
                return True
            else:
                print(f"[!] Logout returned status: {resp.status_code}")
                return False
        except Exception as e:
            print(f"[!] Error during logout: {e}")
            # Clear cookies even on error
            self.session.cookies.clear()
            return False