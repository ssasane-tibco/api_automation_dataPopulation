import json
import urllib.parse

class TenantService:
    def __init__(self, auth_instance):
        self.auth = auth_instance
        self.session = auth_instance.session

    def get_api_headers(self):
        """
        Get common API headers with CSRF token.

        Returns:
            dict: API headers
        """
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Referer': f"{self.auth.host_idm}/cp/app/dataplanes"
        }

        # Add CSRF token if available
        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        return headers

    def provision_subscription(self, host_prefix, idp_host):
        """Provisions a subscription using the established session."""
        provision_url = f"{idp_host}/admin/v1/cpass-subscriptions"
        
        headers = {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json',
            'origin': idp_host,
            'referer': f"{idp_host}/admin/app/subscriptions/provision",
            'x-requested-with': 'XMLHttpRequest'
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        payload = {
            "userDetails": {
                "firstName": "TIBCO",
                "lastName": "Platform",
                "email": self.auth.username,
                "country": "US",
                "state": "CA"
            },
            "accountDetails": {
                "companyName": "TIBCO",
                "ownerLimit": 10,
                "hostPrefix": host_prefix,
                "comment": ""
            },
            "useDefaultIDP": True
        }
        
        try:
            resp = self.session.post(provision_url, headers=headers, json=payload, timeout=30)
            if resp.status_code in [200, 201]:
                print(f"[+] Subscription for {host_prefix} created.")
                return True
            
            # Handle "Already exists" - check body content
            resp_json = resp.json() if resp.text else {}
            if resp.status_code == 409 or "already exists" in str(resp_json).lower():
                print(f"[*] Subscription for {host_prefix} already exists.")
                return True
            else:
                print(f"[!] Provisioning failed: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"[!] Error during provisioning: {e}")
        return False

    def get_user_details(self, params):
        """Listing CP Host Account Users."""
        url = f"{self.auth.host_idm}/cp/v1/account/users"
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Referer': f"{self.auth.host_idm}/cp/app/manage/users"
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"[!] User list API failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:200]}")
        except Exception as e:
            print(f"[!] Error fetching users: {e}")
        return None

    def get_specific_user(self, email):
        """Get specific user details by email."""
        users_data = self.get_user_details({'order-by': '', 'page': '1', 'limit': '100', 'person': ''})
        if users_data and users_data.get('users'):
            for user in users_data['users']:
                if user.get('email') == email:
                    return user
        return None

    def invite_new_user(self, email):
        """
        Invites a new user to the tenant host with a full set of permissions.
        Updated to match the specific PUT request and payload from curl.
        """
        url = f"{self.auth.host_idm}/cp/v1/invite/members"
        
        # Updated headers to match curl sample
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Origin': self.auth.host_idm,
            'Referer': f"{self.auth.host_idm}/cp/app/manage/assign-permissions",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive'
        }

        # Apply CSRF token if present
        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        # Expanded permissions payload as per the curl sample
        payload = {
            "action": "invite",
            "emails": [email],
            "permissions": [
                {"roleId": "CAPABILITY_USER", "exclude": False, "dataplaneId": "*", "instanceId": "*"},
                {"roleId": "CAPABILITY_ADMIN", "exclude": False, "dataplaneId": "*", "instanceId": "*"},
                {"roleId": "DEV_OPS", "exclude": False, "dataplaneId": "*", "instanceId": "*"},
                {"roleId": "BROWSE_ASSIGNMENTS", "exclude": False},
                {"roleId": "PLATFORM_OPS", "exclude": False, "dataplaneId": "*", "instanceId": "*"},
                {"roleId": "TEAM_ADMIN", "exclude": False},
                {"roleId": "IDP_MANAGER", "exclude": False},
                {"roleId": "OWNER", "exclude": False}
            ],
            "allowTibcoAuthentication": True
        }

        # ====== DEBUG: REQUEST PAYLOAD ======
        # print(f"\n[DEBUG] Invitation Request Payload:")
        # import json as json_module
        # print(json_module.dumps(payload, indent=4))
        # print(f"[DEBUG] Target URL: {url}")
        # print(f"[DEBUG] CSRF Token (x-xsrf-token): {tsc_value if tsc_value else 'None'}\n")
        # ====================================

        try:
            # Using PUT as per the sample curl provided
            resp = self.session.put(url, headers=headers, json=payload, timeout=30)
            
            # ====== DEBUG LOGGING START ======
            # print(f"\n{'='*60}")
            # print(f"[DEBUG] Invitation API Call Details")
            # print(f"{'='*60}")
            # print(f"[DEBUG] Request URL: {url}")
            # print(f"[DEBUG] Request Method: PUT")
            # print(f"[DEBUG] Response Status Code: {resp.status_code}")
            # print(f"[DEBUG] Response Headers:")
            # for header, value in resp.headers.items():
            #     print(f"        {header}: {value}")
            # print(f"\n[DEBUG] Raw Response Text:")
            # print(f"        {resp.text}")

            # Try to parse as JSON for pretty printing
            # try:
            #     import json as json_module
            #     response_json = resp.json()
            #     print(f"\n[DEBUG] Parsed JSON Response:")
            #     print(json_module.dumps(response_json, indent=4))
            # except:
            #     print(f"[DEBUG] (Response is not valid JSON)")

            # print(f"{'='*60}\n")
            # ====== DEBUG LOGGING END ======

            # Original response logging
            # print(f"[*] Invitation API Response: {resp.text}")

            if resp.status_code in [200, 201, 204]:
                # Log the roles assigned for verification
                role_ids = [p['roleId'] for p in payload['permissions']]
                print(f"[+] Successfully invited user: {email} with permissions: {', '.join(role_ids)}")
                return True
            else:
                print(f"[!] Failed to invite user. Status: {resp.status_code}")
                return False
        except Exception as e:
            print(f"[!] Error during user invitation: {e}")
            import traceback
            print(f"[DEBUG] Full traceback:")
            traceback.print_exc()
            return False

    def get_helm_resource_instance_id(self, resource_name=None):
        """
        Get Helm repository resource instance ID.
        Required for dataplane registration.

        Args:
            resource_name (str): Optional - specific resource name to find. If None, returns first available.

        Returns:
            str: Helm resource instance ID or empty string if failed
        """
        url = f"{self.auth.host_idm}/cp/v1/resource-instances-details"

        params = {
            'scope': 'SUBSCRIPTION',
            'resourceLevel': 'PLATFORM',
            'resourceId': 'HELMREPO'
        }

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Referer': f"{self.auth.host_idm}/cp/app/register/k8s"
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                response_data = resp.json()

                # Response structure: {"data": [{"resource_instance_id": "...", "resource_instance_name": "...", ...}]}
                if response_data and 'data' in response_data and len(response_data['data']) > 0:
                    resources = response_data['data']
                    print(f"[+] Found {len(resources)} Helm repository resources")

                    # If resource_name is specified, find that specific resource
                    if resource_name:
                        for resource in resources:
                            if resource.get('resource_instance_name') == resource_name:
                                resource_id = resource.get('resource_instance_id', '')
                                print(f"[+] Found resource '{resource_name}' with ID: {resource_id}")
                                return resource_id
                        print(f"[!] Resource '{resource_name}' not found")
                        return ''

                    # Otherwise return first available resource
                    first_resource = resources[0]
                    resource_id = first_resource.get('resource_instance_id', '')
                    resource_name = first_resource.get('resource_instance_name', 'Unknown')
                    print(f"[+] Using Helm resource: {resource_name} (ID: {resource_id})")
                    return resource_id
                else:
                    print("[!] No Helm repository resources found in response")
                    return ''
            else:
                print(f"[!] Failed to get Helm resources. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return ''
        except Exception as e:
            print(f"[!] Error fetching Helm resources: {e}")
            return ''

    def register_dataplane(self, dataplane_config):
        """
        Register a new dataplane (K8s) on the Control Plane.

        Args:
            dataplane_config (dict): Dataplane configuration with the following structure:
                {
                    "name": "Dp1",
                    "description": "test",
                    "namespace": "sd",
                    "serviceAccountName": "sdf",
                    "helmResourceInstanceId": "d5ic0md4runc73anjlvg",
                    "isFluentBitEnabled": true,
                    "enableClusterScopedPerm": true,
                    "customContainerRegistry": false
                }

        Returns:
            dict: Response containing commands to execute, or None if failed
                {
                    "success": True/False,
                    "commands": ["command1", "command2", ...],
                    "dataplane_id": "...",
                    "response": {...}
                }
        """
        url = f"{self.auth.host_idm}/cp/v1/data-planes"

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json',
            'Origin': self.auth.host_idm,
            'Referer': f"{self.auth.host_idm}/cp/app/register/k8s",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }

        # Apply CSRF token if present
        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        # Check if helmResourceInstanceId is provided, if not try to fetch from API
        helm_resource_id = dataplane_config.get("helmResourceInstanceId", "")
        helm_repo_resource = None

        if not helm_resource_id:
            print("[*] No Helm resource ID provided, fetching from API...")
            helm_resource_id = self.get_helm_resource_instance_id()

            if helm_resource_id:
                print(f"[+] Retrieved Helm resource instance ID: {helm_resource_id}")
            else:
                # If still no helm_resource_id, create a helmRepoResource object instead
                print("[*] No Helm resource instance found, creating helmRepoResource object")
                print("[*] Using default TIBCO Platform chart configuration")

                # Create helmRepoResource as alternative to helmResourceInstanceId
                helm_repo_resource = {
                    "chartName": dataplane_config.get("helmChartName", "dp-core-infrastructure"),
                    "chartVersion": dataplane_config.get("helmChartVersion", "1.2.0"),
                    "repoName": dataplane_config.get("helmRepoName", "tibco-platform"),
                    "repoUrl": dataplane_config.get("helmRepoUrl", "https://tibcosoftware.github.io/tp-helm-charts")
                }
                print(f"[+] Created helmRepoResource with chart: {helm_repo_resource['chartName']}")

        # Build the payload from config
        payload = {
            "name": dataplane_config.get("name", "Dp1"),
            "description": dataplane_config.get("description", ""),
            "hostCloudType": "k8s",
            "namespace": dataplane_config.get("namespace", "default"),
            "status": "created",
            "eula": True,
            "serviceAccountResource": {
                "resourceInstanceMetadata": {
                    "fields": [
                        {
                            "dataType": "string",
                            "name": "Service Account Name",
                            "required": True,
                            "key": "serviceAccountName",
                            "value": dataplane_config.get("serviceAccountName", "tibco-sa")
                        },
                        {
                            "dataType": "string",
                            "name": "Namespace",
                            "required": True,
                            "key": "namespace",
                            "value": dataplane_config.get("namespace", "default")
                        }
                    ]
                }
            },
            "k8sDPConfig": {
                "isFluentBitEnabled": dataplane_config.get("isFluentBitEnabled", True),
                "enableClusterScopedPerm": dataplane_config.get("enableClusterScopedPerm", True)
            },
            "customContainerRegistry": dataplane_config.get("customContainerRegistry", False)
        }

        # Add either helmResourceInstanceId or helmRepoResource (API requires one of them)
        if helm_resource_id:
            payload["helmResourceInstanceId"] = helm_resource_id
            print(f"[*] Using helmResourceInstanceId: {helm_resource_id}")
        elif helm_repo_resource:
            payload["helmRepoResource"] = helm_repo_resource
            print(f"[*] Using helmRepoResource with chart: {helm_repo_resource['chartName']}")
        else:
            print("[!] WARNING: Neither helmResourceInstanceId nor helmRepoResource is set!")

        print(f"\n[*] Registering dataplane: {payload['name']}")
        print(f"    Namespace: {payload['namespace']}")
        print(f"    Service Account: {dataplane_config.get('serviceAccountName', 'tibco-sa')}")

        # Print request payload for debugging
        print(f"\n{'='*60}")
        print(f"[DEBUG] Request Payload")
        print(f"{'='*60}")
        print(json.dumps(payload, indent=2))
        print(f"{'='*60}\n")

        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=30)

            # Print full response for debugging
            print(f"\n{'='*60}")
            print(f"[DEBUG] API Response Details")
            print(f"{'='*60}")
            print(f"Status Code: {resp.status_code}")
            print(f"Response Headers: {dict(resp.headers)}")
            print(f"\nResponse Body:")
            print(resp.text)
            print(f"{'='*60}\n")

            if resp.status_code in [200, 201]:
                print(f"[+] Dataplane '{payload['name']}' registered successfully!")

                # Parse response to extract commands
                try:
                    response_json = resp.json()

                    # Debug: Print response keys to understand structure
                    print(f"[*] Response contains keys: {list(response_json.keys())}")

                    # Extract commands array from response (try multiple locations)
                    commands = []

                    # Try direct 'commands' field
                    if 'commands' in response_json:
                        raw_commands = response_json['commands']
                        print(f"[+] Extracted {len(raw_commands)} installation commands from 'commands' field")

                        # Commands may be objects with 'cmd', 'id', 'desc' fields
                        # Extract just the command strings
                        for item in raw_commands:
                            if isinstance(item, dict) and 'cmd' in item:
                                commands.append(item['cmd'])  # Extract the actual command string
                            elif isinstance(item, str):
                                commands.append(item)  # Already a string

                        print(f"[+] Parsed {len(commands)} executable command strings")

                    # Try nested locations (some APIs return commands in different structures)
                    elif 'data' in response_json and 'commands' in response_json['data']:
                        raw_commands = response_json['data']['commands']
                        print(f"[+] Extracted {len(raw_commands)} installation commands from 'data.commands' field")

                        for item in raw_commands:
                            if isinstance(item, dict) and 'cmd' in item:
                                commands.append(item['cmd'])
                            elif isinstance(item, str):
                                commands.append(item)

                    elif 'installationCommands' in response_json:
                        raw_commands = response_json['installationCommands']
                        print(f"[+] Extracted {len(raw_commands)} installation commands from 'installationCommands' field")

                        for item in raw_commands:
                            if isinstance(item, dict) and 'cmd' in item:
                                commands.append(item['cmd'])
                            elif isinstance(item, str):
                                commands.append(item)

                    else:
                        print(f"[!] No 'commands' field found in response")
                        print(f"[*] Full response structure: {json.dumps(response_json, indent=2)[:500]}...")

                    # Get dataplane ID if available
                    dataplane_id = response_json.get('dp_id', response_json.get('id', response_json.get('dataplaneId', response_json.get('dpId', ''))))
                    if dataplane_id:
                        print(f"[+] Dataplane ID: {dataplane_id}")

                    return {
                        "success": True,
                        "commands": commands,
                        "dataplane_id": dataplane_id,
                        "response": response_json
                    }
                except json.JSONDecodeError as e:
                    print(f"[!] Failed to parse response JSON: {e}")
                    print(f"[*] Raw response: {resp.text[:500]}")
                    return {
                        "success": True,
                        "commands": [],
                        "dataplane_id": "",
                        "response": {"raw": resp.text}
                    }
            else:
                print(f"[!] Dataplane registration failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return {
                    "success": False,
                    "commands": [],
                    "dataplane_id": "",
                    "response": {"error": resp.text}
                }
        except Exception as e:
            print(f"[!] Error during dataplane registration: {e}")
            import traceback
            traceback.print_exc()
            return None

    def add_activation_server(self, activation_server_config):
        """
        Add an activation server to the Control Plane.

        Args:
            activation_server_config (dict): Activation server configuration with the following structure:
                {
                    "name": "https://ip-10-180-177-30.eu-west-1.compute.internal:7070",
                    "url": "https://ip-10-180-177-30.eu-west-1.compute.internal:7070",
                    "version": "1.8.0"
                }

        Returns:
            dict: Response containing resource_instance_id or None if failed
                {
                    "success": True/False,
                    "resource_instance_id": "...",
                    "response": {...}
                }
        """
        url = f"{self.auth.host_idm}/cp/api/v1/resources/instances/ACTIVATION_SERVER"

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'Origin': self.auth.host_idm,
            'Referer': f"{self.auth.host_idm}/cp/app/global-configuration/activation",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Priority': 'u=0',
            'TE': 'trailers'
        }

        # Apply CSRF token if present
        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        # Build the payload from config
        payload = {
            "name": activation_server_config.get("name"),
            "url": activation_server_config.get("url"),
            "version": activation_server_config.get("version", "1.8.0")
        }

        print(f"\n[*] Adding activation server: {payload['name']}")
        print(f"    URL: {payload['url']}")
        print(f"    Version: {payload['version']}")

        # Print request payload for debugging
        print(f"\n{'='*60}")
        print(f"[DEBUG] Request Payload")
        print(f"{'='*60}")
        print(json.dumps(payload, indent=2))
        print(f"{'='*60}\n")

        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=30)

            # Print full response for debugging
            print(f"\n{'='*60}")
            print(f"[DEBUG] API Response Details")
            print(f"{'='*60}")
            print(f"Status Code: {resp.status_code}")
            print(f"Response Headers: {dict(resp.headers)}")
            print(f"\nResponse Body:")
            print(resp.text)
            print(f"{'='*60}\n")

            if resp.status_code in [200, 201]:
                print(f"[+] Activation server '{payload['name']}' added successfully!")

                # Parse response to extract resource_instance_id
                try:
                    response_json = resp.json()

                    # Debug: Print response keys to understand structure
                    print(f"[*] Response contains keys: {list(response_json.keys())}")

                    # Extract resource_instance_id from response
                    resource_instance_id = ""

                    # Check expected response structure: {"status":"success","response":{"resource_instance_id":"..."}}
                    if response_json.get('status') == 'success' and 'response' in response_json:
                        resource_instance_id = response_json['response'].get('resource_instance_id', '')
                        if resource_instance_id:
                            print(f"[+] Resource Instance ID: {resource_instance_id}")
                        else:
                            print(f"[!] No resource_instance_id found in response")
                    else:
                        print(f"[!] Unexpected response structure")
                        print(f"[*] Full response: {json.dumps(response_json, indent=2)[:500]}...")

                    return {
                        "success": True,
                        "resource_instance_id": resource_instance_id,
                        "response": response_json
                    }
                except json.JSONDecodeError as e:
                    print(f"[!] Failed to parse response JSON: {e}")
                    print(f"[*] Raw response: {resp.text[:500]}")
                    return {
                        "success": True,
                        "resource_instance_id": "",
                        "response": {"raw": resp.text}
                    }
            else:
                print(f"[!] Activation server addition failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return {
                    "success": False,
                    "resource_instance_id": "",
                    "response": {"error": resp.text}
                }
        except Exception as e:
            print(f"[!] Error during activation server addition: {e}")
            import traceback
            traceback.print_exc()
            return None

    def associate_activation_server_to_dataplane(self, dataplane_id, activation_server_resource_id):
        """
        Associate an activation server with a specific dataplane.
        This should be called after adding the global activation server and before provisioning capabilities.

        Args:
            dataplane_id (str): The dataplane ID to associate with
            activation_server_resource_id (str): The resource instance ID of the activation server

        Returns:
            dict: Response containing success status
                {
                    "success": True/False,
                    "message": "...",
                    "response": {...}
                }
        """
        url = f"{self.auth.host_idm}/cp/api/v1/data-planes/{dataplane_id}/resource-association"

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'Origin': self.auth.host_idm,
            'Referer': f"{self.auth.host_idm}/cp/app/configuration/activation/data-plane/{dataplane_id}",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Priority': 'u=0',
            'TE': 'trailers'
        }

        # Apply CSRF token if present
        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        # Build the payload
        payload = {
            "resource-instance-id": activation_server_resource_id,
            "resource-type": "ACTIVATION_SERVER",
            "operation": "link",
            "scope": "SUBSCRIPTION",
            "licenseType": "TIBCO_ACTIVATION_SERVICE"
        }

        print(f"\n[*] Associating activation server with dataplane: {dataplane_id}")
        print(f"    Activation Server Resource ID: {activation_server_resource_id}")

        # Print request payload for debugging
        print(f"\n{'='*60}")
        print(f"[DEBUG] Associate Activation Server Request")
        print(f"{'='*60}")
        print(f"URL: {url}")
        print(f"Payload:")
        print(json.dumps(payload, indent=2))
        print(f"{'='*60}\n")

        try:
            resp = self.session.put(url, headers=headers, json=payload, timeout=30)

            # Print full response for debugging
            print(f"\n{'='*60}")
            print(f"[DEBUG] API Response Details")
            print(f"{'='*60}")
            print(f"Status Code: {resp.status_code}")
            print(f"Response Body:")
            print(resp.text)
            print(f"{'='*60}\n")

            if resp.status_code in [200, 201]:
                print(f"[+] Activation server associated successfully with dataplane!")

                # Parse response
                try:
                    response_json = resp.json()

                    # Extract message
                    message = ""
                    if response_json.get('status') == 'success' and 'response' in response_json:
                        message = response_json['response'].get('message', '')
                        print(f"[+] {message}")

                    return {
                        "success": True,
                        "message": message,
                        "response": response_json
                    }
                except json.JSONDecodeError as e:
                    print(f"[!] Failed to parse response JSON: {e}")
                    return {
                        "success": True,
                        "message": "Activation server linked successfully",
                        "response": {"raw": resp.text}
                    }
            else:
                print(f"[!] Activation server association failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return {
                    "success": False,
                    "message": f"HTTP {resp.status_code}",
                    "response": {"error": resp.text}
                }
        except Exception as e:
            print(f"[!] Error during activation server association: {e}")
            import traceback
            traceback.print_exc()
            return None

    def use_global_activation_server(self, dataplanes, activation_server_resource_id):
        """
        Associate the global activation server with multiple dataplanes.
        This should be called after adding the global activation server and before provisioning capabilities.

        Args:
            dataplanes (list): List of dataplane dictionaries with 'id' and 'name' keys
            activation_server_resource_id (str): The resource instance ID of the activation server

        Returns:
            dict: Summary of associations
                {
                    "success": True/False,
                    "total": int,
                    "successful": int,
                    "failed": int,
                    "details": [...]
                }
        """
        print(f"\n{'='*60}")
        print(f"[*] Associating Activation Server with Dataplanes")
        print(f"{'='*60}")
        print(f"[*] Activation Server Resource ID: {activation_server_resource_id}")
        print(f"[*] Number of dataplanes: {len(dataplanes)}")
        print(f"{'='*60}\n")

        results = {
            "success": True,
            "total": len(dataplanes),
            "successful": 0,
            "failed": 0,
            "details": []
        }

        for dp in dataplanes:
            dp_id = dp.get('id')
            dp_name = dp.get('name', 'Unknown')

            print(f"\n[*] Associating activation server with dataplane: {dp_name}")
            print(f"    Dataplane ID: {dp_id}")

            result = self.associate_activation_server_to_dataplane(dp_id, activation_server_resource_id)

            if result and result.get("success"):
                results["successful"] += 1
                results["details"].append({
                    "dataplane_id": dp_id,
                    "dataplane_name": dp_name,
                    "status": "success"
                })
                print(f"[+] Activation server associated successfully with {dp_name}")
            else:
                results["failed"] += 1
                results["success"] = False
                results["details"].append({
                    "dataplane_id": dp_id,
                    "dataplane_name": dp_name,
                    "status": "failed",
                    "error": result.get("message") if result else "Unknown error"
                })
                print(f"[!] Failed to associate activation server with {dp_name}")

        # Print summary
        print(f"\n{'='*60}")
        print(f"[*] Activation Server Association Summary:")
        print(f"{'='*60}")
        print(f"    Total Dataplanes: {results['total']}")
        print(f"    Successful: {results['successful']}")
        print(f"    Failed: {results['failed']}")
        print(f"{'='*60}\n")

        return results

    def check_dataplane_status(self, dataplane_id=None, max_wait_seconds=120, poll_interval_seconds=10):
        """
        Check dataplane status and wait until it becomes green or timeout occurs.

        Args:
            dataplane_id (str): Optional - Specific dataplane ID to check. If None, checks all dataplanes.
            max_wait_seconds (int): Maximum time to wait for green status (default: 120 seconds)
            poll_interval_seconds (int): Time between status checks (default: 10 seconds)

        Returns:
            dict: Status information
                {
                    "success": True/False,
                    "all_green": True/False,
                    "dataplanes": [...],
                    "elapsed_time": seconds,
                    "attempts": number
                }
        """
        import time

        url = f"{self.auth.host_idm}/cp/v1/data-planes-status"

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json',
            'Referer': f"{self.auth.host_idm}/cp/app/subscription/data-planes?page=1",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }

        # Apply CSRF token if present
        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        print(f"\n[*] Checking dataplane status...")
        if dataplane_id:
            print(f"    Target Dataplane ID: {dataplane_id}")
        print(f"    Max Wait Time: {max_wait_seconds} seconds")
        print(f"    Poll Interval: {poll_interval_seconds} seconds")

        start_time = time.time()
        attempts = 0
        all_green = False

        while True:
            attempts += 1
            elapsed_time = time.time() - start_time

            # Check if timeout reached
            if elapsed_time >= max_wait_seconds:
                print(f"\n[!] Timeout reached after {elapsed_time:.1f} seconds ({attempts} attempts)")
                break

            try:
                resp = self.session.get(url, headers=headers, timeout=30)

                if resp.status_code == 200:
                    response_json = resp.json()
                    dataplanes = response_json.get('dataplanes', [])

                    if not dataplanes:
                        print(f"[!] Attempt {attempts}: No dataplanes found in response")
                        time.sleep(poll_interval_seconds)
                        continue

                    # Print status for all dataplanes
                    print(f"\n{'='*80}")
                    print(f"[*] Attempt {attempts} | Elapsed: {elapsed_time:.1f}s | Dataplanes Found: {len(dataplanes)}")
                    print(f"{'='*80}")

                    all_green = True
                    target_found = False
                    dataplane_statuses = []

                    for idx, dp in enumerate(dataplanes, 1):
                        dp_id = dp.get('dp_id', 'Unknown')
                        status = dp.get('status', 'unknown')
                        message = dp.get('message', '')
                        tibtunnel = dp.get('tibtunnel_connected', False)
                        capabilities = dp.get('capabilities', [])

                        # Check if this is the target dataplane (if specified)
                        if dataplane_id and dp_id != dataplane_id:
                            continue

                        target_found = True if dataplane_id else True

                        # Get status emoji
                        status_emoji = "[OK]" if status == "green" else "[WARN]" if status == "yellow" else "[ERR]"
                        tibtunnel_emoji = "[OK]" if tibtunnel else "[ERR]"

                        print(f"\n    Dataplane #{idx}:")
                        print(f"    |- ID: {dp_id}")
                        print(f"    |- Status: {status_emoji} {status.upper()}")
                        print(f"    |- Tibtunnel: {tibtunnel_emoji} {'Connected' if tibtunnel else 'Disconnected'}")

                        if message:
                            print(f"    |- Message: {message}")

                        # Count capabilities by status
                        cap_green = 0
                        cap_other = 0
                        non_green_caps = []

                        if capabilities:
                            print(f"    '- Capabilities ({len(capabilities)} total):")
                            for cap in capabilities:
                                cap_name = cap.get('capability', 'Unknown')
                                cap_status = cap.get('status', 'unknown')
                                cap_type = cap.get('capability_type', '')

                                cap_emoji = "[OK]" if cap_status == "green" else "[WARN]" if cap_status == "yellow" else "[ERR]"
                                print(f"       |- {cap_emoji} {cap_name} ({cap_type}): {cap_status}")

                                if cap_status == 'green':
                                    cap_green += 1
                                else:
                                    cap_other += 1
                                    non_green_caps.append(f"{cap_name}:{cap_status}")

                                # Check services
                                services = cap.get('services', [])
                                non_green_services = []
                                for service in services:
                                    svc_name = service.get('name', 'Unknown')
                                    svc_status = service.get('status', 'unknown')

                                    if svc_status not in ['green', 'absent']:
                                        svc_emoji = "[WARN]" if svc_status == "yellow" else "[ERR]"
                                        print(f"       |  '- {svc_emoji} Service: {svc_name} ({svc_status})")
                                        non_green_services.append(f"{svc_name}:{svc_status}")
                                        if svc_status != 'green':
                                            all_green = False

                        # Store dataplane status for summary
                        dataplane_statuses.append({
                            "id": dp_id,
                            "status": status,
                            "tibtunnel": tibtunnel,
                            "cap_green": cap_green,
                            "cap_total": len(capabilities),
                            "non_green_caps": non_green_caps
                        })

                        # Check overall dataplane status
                        if status != 'green':
                            all_green = False

                    # Print summary table
                    print(f"\n{'='*80}")
                    print(f"STATUS SUMMARY - Attempt {attempts}")
                    print(f"{'='*80}")
                    print(f"{'ID':<25} | {'Status':<10} | {'Tibtunnel':<10} | {'Capabilities':<20}")
                    print(f"{'-'*80}")

                    for dp_status in dataplane_statuses:
                        status_display = dp_status['status'].upper()
                        status_emoji = "[OK]" if dp_status['status'] == "green" else "[WARN]" if dp_status['status'] == "yellow" else "[ERR]"
                        tibtunnel_display = "Connected" if dp_status['tibtunnel'] else "Disconnected"
                        tibtunnel_emoji = "[OK]" if dp_status['tibtunnel'] else "[ERR]"
                        cap_display = f"{dp_status['cap_green']}/{dp_status['cap_total']} green"

                        print(f"{dp_status['id']:<25} | {status_emoji} {status_display:<8} | {tibtunnel_emoji} {tibtunnel_display:<8} | {cap_display:<20}")

                        # Show non-green capabilities
                        if dp_status['non_green_caps']:
                            print(f"{'':25} | {'':11} | {'':11} | [!] {', '.join(dp_status['non_green_caps'][:3])}")

                    print(f"{'='*80}")

                    green_count = sum(1 for dp in dataplane_statuses if dp['status'] == 'green')
                    yellow_count = sum(1 for dp in dataplane_statuses if dp['status'] == 'yellow')
                    red_count = sum(1 for dp in dataplane_statuses if dp['status'] not in ['green', 'yellow'])

                    print(f"Overall: {green_count} Green | {yellow_count} Yellow | {red_count} Red/Other | Total: {len(dataplane_statuses)}")
                    print(f"{'='*80}\n")

                    # If checking specific dataplane and it's not found
                    if dataplane_id and not target_found:
                        print(f"[!] Target dataplane {dataplane_id} not found in status response")
                        all_green = False

                    # If all dataplanes are green, we're done!
                    if all_green:
                        print(f"\n[+] ALL DATAPLANES ARE GREEN!")
                        print(f"    Total time: {elapsed_time:.1f} seconds")
                        print(f"    Total attempts: {attempts}")
                        print(f"    Dataplanes checked: {len(dataplane_statuses)}")

                        return {
                            "success": True,
                            "all_green": True,
                            "dataplanes": dataplanes,
                            "dataplane_statuses": dataplane_statuses,
                            "elapsed_time": elapsed_time,
                            "attempts": attempts
                        }
                    else:
                        print(f"[*] Not all dataplanes are green yet. Waiting {poll_interval_seconds} seconds before next check...")
                        time.sleep(poll_interval_seconds)

                else:
                    print(f"[!] Attempt {attempts}: API returned status {resp.status_code}")
                    print(f"    Response: {resp.text[:200]}")
                    time.sleep(poll_interval_seconds)

            except Exception as e:
                print(f"[!] Attempt {attempts}: Error checking status: {e}")
                time.sleep(poll_interval_seconds)

        # Timeout reached
        final_elapsed = time.time() - start_time
        print(f"\n{'='*80}")
        print(f"[!] TIMEOUT REACHED after {final_elapsed:.1f} seconds ({attempts} attempts)")
        print(f"{'='*80}")

        # Try to get final status
        try:
            resp = self.session.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                response_json = resp.json()
                dataplanes = response_json.get('dataplanes', [])

                if dataplanes:
                    # Show final status summary
                    print(f"\n[*] FINAL STATUS SUMMARY")
                    print(f"{'='*80}")
                    print(f"{'ID':<25} | {'Status':<10} | {'Tibtunnel':<10} | {'Capabilities':<20}")
                    print(f"{'-'*80}")

                    dataplane_statuses = []
                    for dp in dataplanes:
                        dp_id = dp.get('dp_id', 'Unknown')
                        status = dp.get('status', 'unknown')
                        tibtunnel = dp.get('tibtunnel_connected', False)
                        capabilities = dp.get('capabilities', [])

                        cap_green = sum(1 for cap in capabilities if cap.get('status') == 'green')
                        cap_total = len(capabilities)

                        status_display = status.upper()
                        status_emoji = "[OK]" if status == "green" else "[WARN]" if status == "yellow" else "[ERR]"
                        tibtunnel_display = "Connected" if tibtunnel else "Disconnected"
                        tibtunnel_emoji = "[OK]" if tibtunnel else "[ERR]"
                        cap_display = f"{cap_green}/{cap_total} green"

                        print(f"{dp_id:<25} | {status_emoji} {status_display:<8} | {tibtunnel_emoji} {tibtunnel_display:<8} | {cap_display:<20}")

                        dataplane_statuses.append({
                            "id": dp_id,
                            "status": status,
                            "tibtunnel": tibtunnel,
                            "cap_green": cap_green,
                            "cap_total": cap_total
                        })

                    print(f"{'='*80}")
                    green_count = sum(1 for dp in dataplane_statuses if dp['status'] == 'green')
                    yellow_count = sum(1 for dp in dataplane_statuses if dp['status'] == 'yellow')
                    red_count = sum(1 for dp in dataplane_statuses if dp['status'] not in ['green', 'yellow'])

                    print(f"Overall: {green_count} Green | {yellow_count} Yellow | {red_count} Red/Other | Total: {len(dataplane_statuses)}")
                    print(f"{'='*80}")
                    print(f"\n[!] Not all dataplanes reached green status within {final_elapsed:.1f} seconds")

                    return {
                        "success": False,
                        "all_green": False,
                        "dataplanes": dataplanes,
                        "dataplane_statuses": dataplane_statuses,
                        "elapsed_time": final_elapsed,
                        "attempts": attempts,
                        "error": "Timeout reached"
                    }
        except Exception as e:
            print(f"[!] Error getting final status: {e}")

        return {
            "success": False,
            "all_green": False,
            "dataplanes": [],
            "dataplane_statuses": [],
            "elapsed_time": final_elapsed,
            "attempts": attempts,
            "error": "Timeout reached"
        }

    def create_storage_resource(self, dataplane_id, storage_config):
        """
        Create a storage resource for a dataplane.

        Args:
            dataplane_id (str): Dataplane ID
            storage_config (dict): Storage configuration containing:
                - name: Resource name
                - description: Resource description
                - storage_class_name: Kubernetes storage class name (e.g., "gp2")

        Returns:
            dict: Result with success status and resource_instance_id
        """
        print(f"\n[*] Creating storage resource...")

        url = f"{self.auth.host_idm}/cp/v1/resource-instances"

        storage_name = storage_config.get('name', 'dpstorage')
        storage_class = storage_config.get('storage_class_name', 'gp2')
        description = storage_config.get('description', 'Dataplane Storage')

        payload = {
            "resourceId": "STORAGE",
            "payload": {
                "description": description,
                "region": "global",
                "resourceInstanceMetadata": {
                    "fields": [
                        {
                            "dataType": "string",
                            "key": "storageClassName",
                            "name": "Storage Class Name",
                            "required": True,
                            "value": storage_class
                        }
                    ]
                },
                "resourceInstanceName": storage_name,
                "resourceLevel": "PLATFORM",
                "scope": "DATAPLANE",
                "scopeId": dataplane_id
            }
        }

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Origin': self.auth.host_idm,
            'Referer': f"{self.auth.host_idm}/cp/app/configuration/resources/data-plane/{dataplane_id}"
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        print(f"    Name: {storage_name}")
        print(f"    Storage Class: {storage_class}")

        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=30)

            if resp.status_code in [200, 201]:
                response_json = resp.json()
                resource_instance_id = response_json.get('resource_instance_id', '')

                if resource_instance_id:
                    print(f"[+] Storage resource created successfully!")
                    print(f"    Resource ID: {resource_instance_id}")
                    return {
                        "success": True,
                        "resource_instance_id": resource_instance_id,
                        "resource_name": storage_name
                    }
                else:
                    print(f"[!] No resource instance ID in response")
                    return {"success": False, "error": "No resource ID returned"}
            else:
                print(f"[!] Storage resource creation failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            print(f"[!] Error creating storage resource: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def create_ingress_resource(self, dataplane_id, ingress_config):
        """
        Create an ingress resource for a dataplane.

        Args:
            dataplane_id (str): Dataplane ID
            ingress_config (dict): Ingress configuration containing:
                - name: Resource name
                - ingress_controller: Controller type (nginx, traefik, kong, etc.)
                - ingress_class_name: Ingress class name
                - fqdn: Fully qualified domain name
                - annotations: Optional annotations (default: "")

        Returns:
            dict: Result with success status and resource_instance_id
        """
        print(f"\n[*] Creating ingress resource...")

        url = f"{self.auth.host_idm}/cp/v1/resource-instances"

        ingress_name = ingress_config.get('name', 'dpingress')
        ingress_controller = ingress_config.get('ingress_controller', 'nginx')
        ingress_class = ingress_config.get('ingress_class_name', 'nginx')
        fqdn = ingress_config.get('fqdn', '')
        annotations = ingress_config.get('annotations', '')

        if not fqdn:
            print(f"[!] FQDN is required for ingress resource")
            return {"success": False, "error": "FQDN is required"}

        payload = {
            "resourceId": "INGRESS",
            "payload": {
                "region": "global",
                "resourceInstanceMetadata": {
                    "fields": [
                        {
                            "dataType": "string",
                            "enum": ["nginx", "kong", "traefik", "openshiftRouter"],
                            "fieldType": "dropdown",
                            "key": "ingressController",
                            "name": "Ingress Controller",
                            "required": True,
                            "value": ingress_controller
                        },
                        {
                            "dataType": "string",
                            "key": "ingressClassName",
                            "maxLength": "63",
                            "name": "Ingress Class Name",
                            "regex": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                            "required": True,
                            "value": ingress_class
                        },
                        {
                            "dataType": "string",
                            "key": "fqdn",
                            "maxLength": "255",
                            "name": "Default FQDN",
                            "regex": "^[a-z0-9]([-a-z0-9][a-z0-9])?(\\.[a-z0-9]([-a-z0-9][a-z0-9])?)*$",
                            "required": True,
                            "value": fqdn
                        },
                        {
                            "dataType": "array",
                            "key": "annotations",
                            "maxLength": "255",
                            "name": "Annotations",
                            "required": False,
                            "value": annotations
                        }
                    ]
                },
                "resourceInstanceName": ingress_name,
                "resourceLevel": "PLATFORM",
                "scope": "DATAPLANE",
                "scopeId": dataplane_id
            }
        }

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Origin': self.auth.host_idm,
            'Referer': f"{self.auth.host_idm}/cp/app/configuration/resources/data-plane/{dataplane_id}"
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        print(f"    Name: {ingress_name}")
        print(f"    Controller: {ingress_controller}")
        print(f"    Class Name: {ingress_class}")
        print(f"    FQDN: {fqdn}")

        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=30)

            if resp.status_code in [200, 201]:
                response_json = resp.json()
                resource_instance_id = response_json.get('resource_instance_id', '')

                if resource_instance_id:
                    print(f"[+] Ingress resource created successfully!")
                    print(f"    Resource ID: {resource_instance_id}")
                    return {
                        "success": True,
                        "resource_instance_id": resource_instance_id,
                        "resource_name": ingress_name,
                        "fqdn": fqdn
                    }
                else:
                    print(f"[!] No resource instance ID in response")
                    return {"success": False, "error": "No resource ID returned"}
            else:
                print(f"[!] Ingress resource creation failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            print(f"[!] Error creating ingress resource: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def get_storage_resource_id(self, dataplane_id, storage_name):
        """
        Get storage resource ID for a dataplane.

        Args:
            dataplane_id (str): Dataplane ID
            storage_name (str): Storage resource name

        Returns:
            str: Storage resource ID or empty string if not found
        """
        url = f"{self.auth.host_idm}/cp/v1/resource-instances-details"

        params = {
            'scope': 'DATAPLANE',
            'resourceLevel': 'PLATFORM',
            'resourceId': 'STORAGE',
            'dataPlaneId': dataplane_id
        }

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Referer': f"{self.auth.host_idm}/cp/app/dataplanes"
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                response_data = resp.json()

                if response_data and 'data' in response_data:
                    for resource in response_data['data']:
                        if resource.get('resource_instance_name') == storage_name:
                            resource_id = resource.get('resource_instance_id', '')
                            print(f"[+] Found existing storage resource '{storage_name}': {resource_id}")
                            return resource_id

                print(f"[!] Storage resource '{storage_name}' not found")
            else:
                print(f"[!] Failed to get storage resources. Status: {resp.status_code}")
        except Exception as e:
            print(f"[!] Error fetching storage resource: {e}")
        return ''

    def get_ingress_resource_id(self, dataplane_id, ingress_name):
        """
        Get ingress resource ID for a dataplane.

        Args:
            dataplane_id (str): Dataplane ID
            ingress_name (str): Ingress resource name

        Returns:
            tuple: (resource_id, fqdn) or ('', '') if not found
        """
        url = f"{self.auth.host_idm}/cp/v1/resource-instances-details"

        params = {
            'scope': 'DATAPLANE',
            'resourceLevel': 'PLATFORM',
            'resourceId': 'INGRESS',
            'dataPlaneId': dataplane_id
        }

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Referer': f"{self.auth.host_idm}/cp/app/dataplanes"
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=30)
            if resp.status_code == 200:
                response_data = resp.json()

                if response_data and 'data' in response_data:
                    for resource in response_data['data']:
                        if resource.get('resource_instance_name') == ingress_name:
                            resource_id = resource.get('resource_instance_id', '')
                            # Get FQDN from metadata
                            metadata = resource.get('resource_instance_metadata', {})
                            fields = metadata.get('fields', [])
                            fqdn = ''
                            for field in fields:
                                if field.get('key') == 'fqdn':
                                    fqdn = field.get('value', '')
                                    break
                            print(f"[+] Found existing ingress resource '{ingress_name}': {resource_id}")
                            if fqdn:
                                print(f"    FQDN: {fqdn}")
                            return resource_id, fqdn

                print(f"[!] Ingress resource '{ingress_name}' not found")
            else:
                print(f"[!] Failed to get ingress resources. Status: {resp.status_code}")
        except Exception as e:
            print(f"[!] Error fetching ingress resource: {e}")
        return '', ''

    def provision_bwce_capability(self, dataplane_id, dataplane_name, bwce_config):
        """
        Provision BWCE capability on a dataplane.

        Args:
            dataplane_id (str): Dataplane ID
            dataplane_name (str): Dataplane name
            bwce_config (dict): BWCE configuration containing:
                - capability_version: BWCE version (e.g., "1.5.0")
                - storage_resource_id: Storage resource instance ID (preferred)
                - ingress_resource_id: Ingress resource instance ID (preferred)
                - storage_resource_name: Storage resource name (fallback for backward compatibility)
                - ingress_resource_name: Ingress resource name (fallback for backward compatibility)
                - ingress_class_name: Ingress class name
                - ingress_controller_name: Ingress controller name
                - enable_fluentbit: Enable fluentbit sidecar
                - timeout_seconds: Provisioning timeout

        Returns:
            dict: Provisioning result with success status and capability instance ID
        """
        print(f"\n[*] Provisioning BWCE capability for dataplane: {dataplane_name}")
        print(f"    Dataplane ID: {dataplane_id}")

        # Get resource IDs - prefer direct IDs, fall back to lookup by name
        storage_resource_id = bwce_config.get('storage_resource_id')
        if not storage_resource_id and bwce_config.get('storage_resource_name'):
            # Fallback: lookup by name for backward compatibility
            storage_resource_id = self.get_storage_resource_id(
                dataplane_id,
                bwce_config.get('storage_resource_name')
            )

        if not storage_resource_id:
            return {
                "success": False,
                "error": f"Storage resource not found (no ID or name provided)"
            }

        ingress_resource_id = bwce_config.get('ingress_resource_id')
        ingress_fqdn = ''
        if not ingress_resource_id and bwce_config.get('ingress_resource_name'):
            # Fallback: lookup by name for backward compatibility
            ingress_resource_id, ingress_fqdn = self.get_ingress_resource_id(
                dataplane_id,
                bwce_config.get('ingress_resource_name')
            )

        if not ingress_resource_id:
            return {
                "success": False,
                "error": f"Ingress resource not found (no ID or name provided)"
            }

        # Build BWCE provisioning payload
        capability_version = bwce_config.get('capability_version', '1.5.0')
        ingress_class_name = bwce_config.get('ingress_class_name', 'nginx')
        ingress_controller_name = bwce_config.get('ingress_controller_name', 'nginx')
        enable_fluentbit = bwce_config.get('enable_fluentbit', True)

        payload = {
            "provision-schema": {
                "path-prefix": f"/tibco/bw/{dataplane_id}",
                "storage-class-resource-instance-id": storage_resource_id,
                "ingress-controller-resource-instance-id": ingress_resource_id,
                "ingress-class-name": ingress_class_name,
                "ingress-controller-name": ingress_controller_name,
                "fluentbit-sidecar-enabled": enable_fluentbit
            }
        }

        print(f"\n[*] BWCE Provisioning Details:")
        print(f"    Version: {capability_version}")
        print(f"    Storage Resource ID: {storage_resource_id}")
        print(f"    Ingress Resource ID: {ingress_resource_id}")
        if ingress_fqdn:
            print(f"    Ingress FQDN: {ingress_fqdn}")
        print(f"    Ingress Class: {ingress_class_name}")
        print(f"    FluentBit Enabled: {enable_fluentbit}")

        # Provision BWCE capability via REST API
        url = f"{self.auth.host_idm}/cp/api/v1/data-planes/{dataplane_id}/capabilities/BWCE"

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json',
            'Origin': self.auth.host_idm,
            'Referer': f"{self.auth.host_idm}/cp/app/dataplanes",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        print(f"\n{'='*60}")
        print(f"[DEBUG] BWCE Provision Request")
        print(f"{'='*60}")
        print(f"URL: {url}")
        print(f"Payload:")
        print(json.dumps(payload, indent=2))
        print(f"{'='*60}\n")

        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=60)

            print(f"\n{'='*60}")
            print(f"[DEBUG] BWCE Provision Response")
            print(f"{'='*60}")
            print(f"Status Code: {resp.status_code}")
            print(f"Response Body:")
            print(resp.text)
            print(f"{'='*60}\n")

            if resp.status_code in [200, 201]:
                response_json = resp.json()
                capability_instance_id = response_json.get('response', {}).get('capabilityInstanceId', '')

                if capability_instance_id:
                    print(f"[+] BWCE capability provisioning initiated successfully!")
                    print(f"    Capability Instance ID: {capability_instance_id}")

                    return {
                        "success": True,
                        "capability_instance_id": capability_instance_id,
                        "dataplane_id": dataplane_id,
                        "dataplane_name": dataplane_name,
                        "response": response_json
                    }
                else:
                    print(f"[!] No capability instance ID in response")
                    return {
                        "success": False,
                        "error": "No capability instance ID returned",
                        "response": response_json
                    }
            else:
                print(f"[!] BWCE provisioning failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}",
                    "response": resp.text
                }
        except Exception as e:
            print(f"[!] Error during BWCE provisioning: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def provision_flogo_capability(self, dataplane_id, dataplane_name, flogo_config):
        """
        Provision Flogo capability on a dataplane.

        Args:
            dataplane_id (str): Dataplane ID
            dataplane_name (str): Dataplane name
            flogo_config (dict): Flogo configuration containing:
                - capability_version: Flogo version (e.g., "1.5.0")
                - storage_resource_id: Storage resource instance ID (preferred)
                - ingress_resource_id: Ingress resource instance ID (preferred)
                - storage_resource_name: Storage resource name (fallback for backward compatibility)
                - ingress_resource_name: Ingress resource name (fallback for backward compatibility)
                - ingress_class_name: Ingress class name
                - ingress_controller_name: Ingress controller name
                - enable_fluentbit: Enable fluentbit sidecar
                - timeout_seconds: Provisioning timeout

        Returns:
            dict: Provisioning result with success status and capability instance ID
        """
        print(f"\n[*] Provisioning Flogo capability for dataplane: {dataplane_name}")
        print(f"    Dataplane ID: {dataplane_id}")

        # Get resource IDs - prefer direct IDs, fall back to lookup by name
        storage_resource_id = flogo_config.get('storage_resource_id')
        if not storage_resource_id and flogo_config.get('storage_resource_name'):
            # Fallback: lookup by name for backward compatibility
            storage_resource_id = self.get_storage_resource_id(
                dataplane_id,
                flogo_config.get('storage_resource_name')
            )

        if not storage_resource_id:
            return {
                "success": False,
                "error": f"Storage resource not found (no ID or name provided)"
            }

        ingress_resource_id = flogo_config.get('ingress_resource_id')
        ingress_fqdn = ''
        if not ingress_resource_id and flogo_config.get('ingress_resource_name'):
            # Fallback: lookup by name for backward compatibility
            ingress_resource_id, ingress_fqdn = self.get_ingress_resource_id(
                dataplane_id,
                flogo_config.get('ingress_resource_name')
            )

        if not ingress_resource_id:
            return {
                "success": False,
                "error": f"Ingress resource not found (no ID or name provided)"
            }

        # Build Flogo provisioning payload
        capability_version = flogo_config.get('capability_version', '1.5.0')
        ingress_class_name = flogo_config.get('ingress_class_name', 'nginx')
        ingress_controller_name = flogo_config.get('ingress_controller_name', 'nginx')
        enable_fluentbit = flogo_config.get('enable_fluentbit', True)

        payload = {
            "provision-schema": {
                "path-prefix": f"/tibco/flogo/{dataplane_id}",
                "storage-class-resource-instance-id": storage_resource_id,
                "ingress-controller-resource-instance-id": ingress_resource_id,
                "ingress-class-name": ingress_class_name,
                "ingress-controller-name": ingress_controller_name,
                "fluentbit-sidecar-enabled": enable_fluentbit
            }
        }

        print(f"\n[*] Flogo Provisioning Details:")
        print(f"    Version: {capability_version}")
        print(f"    Storage Resource ID: {storage_resource_id}")
        print(f"    Ingress Resource ID: {ingress_resource_id}")
        if ingress_fqdn:
            print(f"    Ingress FQDN: {ingress_fqdn}")
        print(f"    Ingress Class: {ingress_class_name}")
        print(f"    FluentBit Enabled: {enable_fluentbit}")

        # Provision Flogo capability via REST API
        url = f"{self.auth.host_idm}/cp/api/v1/data-planes/{dataplane_id}/capabilities/FLOGO"

        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Content-Type': 'application/json',
            'Origin': self.auth.host_idm,
            'Referer': f"{self.auth.host_idm}/cp/app/dataplanes",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) Gecko/20100101 Firefox/146.0',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }

        tsc_value = self.session.cookies.get('tsc')
        if tsc_value:
            headers['x-xsrf-token'] = tsc_value

        print(f"\n{'='*60}")
        print(f"[DEBUG] Flogo Provision Request")
        print(f"{'='*60}")
        print(f"URL: {url}")
        print(f"Payload:")
        print(json.dumps(payload, indent=2))
        print(f"{'='*60}\n")

        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=60)

            print(f"\n{'='*60}")
            print(f"[DEBUG] Flogo Provision Response")
            print(f"{'='*60}")
            print(f"Status Code: {resp.status_code}")
            print(f"Response Body:")
            print(resp.text)
            print(f"{'='*60}\n")

            if resp.status_code in [200, 201]:
                response_json = resp.json()
                capability_instance_id = response_json.get('response', {}).get('capabilityInstanceId', '')

                if capability_instance_id:
                    print(f"[+] Flogo capability provisioning initiated successfully!")
                    print(f"    Capability Instance ID: {capability_instance_id}")

                    return {
                        "success": True,
                        "capability_instance_id": capability_instance_id,
                        "dataplane_id": dataplane_id,
                        "dataplane_name": dataplane_name,
                        "response": response_json
                    }
                else:
                    print(f"[!] No capability instance ID in response")
                    return {
                        "success": False,
                        "error": "No capability instance ID returned",
                        "response": response_json
                    }
            else:
                print(f"[!] Flogo provisioning failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}",
                    "response": resp.text
                }
        except Exception as e:
            print(f"[!] Error during Flogo provisioning: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def provision_bwce_buildtype(self, dataplane_id, capability_instance_id, version="6.12.0-HF1"):
        """
        Provision BWCE buildtype/version templates to the data plane.
        This is MANDATORY before deploying any BWCE applications.

        Args:
            dataplane_id (str): Data plane ID
            capability_instance_id (str): BWCE capability instance ID
            version (str): BWCE version to provision (default: "6.12.0-HF1")

        Returns:
            dict: Result with success status
        """
        print(f"\n[*] Provisioning BWCE buildtype version: {version}")
        print(f"    Dataplane ID: {dataplane_id}")
        print(f"    Capability Instance ID: {capability_instance_id}")

        # Generate random event ID
        import random
        import string
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=31))
        event_id = f"bwce_{random_suffix}"

        # Build the request
        url = f"{self.auth.host_idm}/cp/bwce/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'capability_instance_id': capability_instance_id
        }

        payload = {
            "dataPlaneId": dataplane_id,
            "path": f"/tibco/agent/integration/{capability_instance_id}/bwprovisioner/private/v1/dp/bw/buildtype/{version}",
            "eventId": event_id,
            "queryParams": {
                "capability_instance_id": capability_instance_id
            },
            "payload": {
                "tags": [],
                "filesList": [
                    {
                        "fileName": "bwapp-deploy-template.yaml",
                        "downloadURL": f"/bwce/buildtypes/{version}/bwapp-deploy-template.yaml"
                    },
                    {
                        "fileName": "bwapp-svc-template.yaml",
                        "downloadURL": f"/bwce/buildtypes/{version}/bwapp-svc-template.yaml"
                    },
                    {
                        "fileName": "metadata.json",
                        "downloadURL": f"/bwce/buildtypes/{version}/metadata.json"
                    }
                ]
            }
        }

        headers = self.get_api_headers()
        headers['Content-Type'] = 'application/json'

        print(f"\n{'='*60}")
        print(f"[DEBUG] BWCE Buildtype Provision Request")
        print(f"{'='*60}")
        print(f"URL: {url}")
        print(f"Params: {params}")
        print(f"Payload:")
        print(json.dumps(payload, indent=2))
        print(f"{'='*60}\n")

        try:
            resp = self.session.post(url, params=params, headers=headers, json=payload, timeout=60)

            print(f"\n{'='*60}")
            print(f"[DEBUG] BWCE Buildtype Provision Response")
            print(f"{'='*60}")
            print(f"Status Code: {resp.status_code}")
            print(f"Response Body:")
            print(resp.text)
            print(f"{'='*60}\n")

            if resp.status_code in [200, 201]:
                response_json = resp.json()

                # Check for success status
                if response_json.get('status') == 'success' or response_json.get('message', '').lower().find('successful') != -1:
                    print(f"[+] BWCE buildtype {version} provisioned successfully!")
                    return {
                        "success": True,
                        "version": version,
                        "response": response_json
                    }
                else:
                    print(f"[!] BWCE buildtype provisioning returned unexpected response")
                    return {
                        "success": False,
                        "error": "Unexpected response format",
                        "response": response_json
                    }
            else:
                print(f"[!] BWCE buildtype provisioning failed. Status: {resp.status_code}")
                print(f"    Response: {resp.text[:300]}")
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}",
                    "response": resp.text
                }
        except Exception as e:
            print(f"[!] Error during BWCE buildtype provisioning: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def check_bwce_capability_status(self, dataplane_id, capability_instance_id, max_wait_seconds=300, poll_interval_seconds=15):
        """
        Check BWCE capability status and wait until it becomes green.

        Args:
            dataplane_id: The dataplane ID
            capability_instance_id: The BWCE capability instance ID
            max_wait_seconds: Maximum time to wait (default 300)
            poll_interval_seconds: Time between checks (default 15)

        Returns:
            dict: Status result with success, status, elapsed_time
        """
        import time

        print(f"\n[*] Checking BWCE capability status...")
        print(f"    Dataplane ID: {dataplane_id}")
        print(f"    Capability Instance ID: {capability_instance_id}")
        print(f"    Max Wait Time: {max_wait_seconds} seconds")
        print(f"    Poll Interval: {poll_interval_seconds} seconds")

        url = f"{self.auth.host_idm}/cp/v1/data-planes/{dataplane_id}/capabilities-status"

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        start_time = time.time()
        attempts = 0

        while True:
            attempts += 1
            elapsed_time = time.time() - start_time

            if elapsed_time >= max_wait_seconds:
                print(f"[!] Timeout after {elapsed_time:.1f} seconds")
                return {
                    "success": False,
                    "status": "timeout",
                    "elapsed_time": elapsed_time,
                    "attempts": attempts
                }

            try:
                resp = self.session.get(url, headers=headers, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    dataplanes = data.get('dataplanes', [])

                    if not dataplanes:
                        print(f"[!] Attempt {attempts}: No dataplanes in response")
                        time.sleep(poll_interval_seconds)
                        continue

                    # Find the dataplane
                    for dp in dataplanes:
                        if dp.get('dp_id') == dataplane_id:
                            capabilities = dp.get('capabilities', [])

                            # Find BWCE capability
                            for cap in capabilities:
                                if cap.get('capability') == 'BWCE' and cap.get('capability_instance_id') == capability_instance_id:
                                    cap_status = cap.get('status', 'unknown')
                                    services = cap.get('services', [])

                                    print(f"\n[*] Attempt {attempts} | Elapsed: {elapsed_time:.1f}s")
                                    print(f"    Capability: BWCE")
                                    print(f"    Status: {'[OK]' if cap_status == 'green' else '[WARN]' if cap_status == 'yellow' else '[ERR]'} {cap_status.upper()}")

                                    if services:
                                        print(f"    Services:")
                                        for svc in services:
                                            svc_name = svc.get('name', 'Unknown')
                                            svc_status = svc.get('status', 'unknown')
                                            svc_emoji = '[OK]' if svc_status == 'green' else '[WARN]' if svc_status == 'yellow' else '[ERR]'
                                            print(f"      {svc_emoji} {svc_name}: {svc_status}")

                                    if cap_status == 'green':
                                        print(f"\n[+] BWCE capability is GREEN!")
                                        print(f"    Total time: {elapsed_time:.1f} seconds")
                                        print(f"    Total attempts: {attempts}")
                                        return {
                                            "success": True,
                                            "status": "green",
                                            "elapsed_time": elapsed_time,
                                            "attempts": attempts
                                        }
                                    else:
                                        print(f"[*] BWCE not green yet, waiting {poll_interval_seconds}s...")
                                        time.sleep(poll_interval_seconds)
                                        break
                            else:
                                print(f"[!] Attempt {attempts}: Capability instance {capability_instance_id} not found in response")
                                print(f"    Available capabilities: {len(capabilities)}")
                                for cap in capabilities:
                                    print(f"      - {cap.get('capability')}: {cap.get('capability_instance_id')}")
                                time.sleep(poll_interval_seconds)
                            break
                    else:
                        print(f"[!] Attempt {attempts}: Dataplane {dataplane_id} not found")
                        time.sleep(poll_interval_seconds)
                else:
                    print(f"[!] Attempt {attempts}: HTTP {resp.status_code}")
                    time.sleep(poll_interval_seconds)

            except Exception as e:
                print(f"[!] Attempt {attempts}: Error - {e}")
                time.sleep(poll_interval_seconds)

    def check_flogo_capability_status(self, dataplane_id, capability_instance_id, max_wait_seconds=300, poll_interval_seconds=15):
        """
        Check Flogo capability status and wait until it becomes green.

        Args:
            dataplane_id: The dataplane ID
            capability_instance_id: The Flogo capability instance ID
            max_wait_seconds: Maximum time to wait (default 300)
            poll_interval_seconds: Time between checks (default 15)

        Returns:
            dict: Status result with success, status, elapsed_time
        """
        import time

        print(f"\n[*] Checking Flogo capability status...")
        print(f"    Dataplane ID: {dataplane_id}")
        print(f"    Capability Instance ID: {capability_instance_id}")
        print(f"    Max Wait Time: {max_wait_seconds} seconds")
        print(f"    Poll Interval: {poll_interval_seconds} seconds")

        url = f"{self.auth.host_idm}/cp/v1/data-planes/{dataplane_id}/capabilities-status"

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        start_time = time.time()
        attempts = 0

        while True:
            attempts += 1
            elapsed_time = time.time() - start_time

            if elapsed_time >= max_wait_seconds:
                print(f"[!] Timeout after {elapsed_time:.1f} seconds")
                return {
                    "success": False,
                    "status": "timeout",
                    "elapsed_time": elapsed_time,
                    "attempts": attempts
                }

            try:
                resp = self.session.get(url, headers=headers, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    dataplanes = data.get('dataplanes', [])

                    if not dataplanes:
                        print(f"[!] Attempt {attempts}: No dataplanes in response")
                        time.sleep(poll_interval_seconds)
                        continue

                    # Find the dataplane
                    for dp in dataplanes:
                        if dp.get('dp_id') == dataplane_id:
                            capabilities = dp.get('capabilities', [])

                            # Find Flogo capability
                            for cap in capabilities:
                                if cap.get('capability') == 'FLOGO' and cap.get('capability_instance_id') == capability_instance_id:
                                    cap_status = cap.get('status', 'unknown')
                                    services = cap.get('services', [])

                                    print(f"\n[*] Attempt {attempts} | Elapsed: {elapsed_time:.1f}s")
                                    print(f"    Capability: FLOGO")
                                    print(f"    Status: {'[OK]' if cap_status == 'green' else '[WARN]' if cap_status == 'yellow' else '[ERR]'} {cap_status.upper()}")

                                    if services:
                                        print(f"    Services:")
                                        for svc in services:
                                            svc_name = svc.get('name', 'Unknown')
                                            svc_status = svc.get('status', 'unknown')
                                            svc_emoji = '[OK]' if svc_status == 'green' else '[WARN]' if svc_status == 'yellow' else '[ERR]'
                                            print(f"      {svc_emoji} {svc_name}: {svc_status}")

                                    if cap_status == 'green':
                                        print(f"\n[+] Flogo capability is GREEN!")
                                        print(f"    Total time: {elapsed_time:.1f} seconds")
                                        print(f"    Total attempts: {attempts}")
                                        return {
                                            "success": True,
                                            "status": "green",
                                            "elapsed_time": elapsed_time,
                                            "attempts": attempts
                                        }
                                    else:
                                        print(f"[*] Flogo not green yet, waiting {poll_interval_seconds}s...")
                                        time.sleep(poll_interval_seconds)
                                        break
                            else:
                                print(f"[!] Attempt {attempts}: Capability instance {capability_instance_id} not found in response")
                                print(f"    Available capabilities: {len(capabilities)}")
                                for cap in capabilities:
                                    print(f"      - {cap.get('capability')}: {cap.get('capability_instance_id')}")
                                time.sleep(poll_interval_seconds)
                            break
                    else:
                        print(f"[!] Attempt {attempts}: Dataplane {dataplane_id} not found")
                        time.sleep(poll_interval_seconds)
                else:
                    print(f"[!] Attempt {attempts}: HTTP {resp.status_code}")
                    time.sleep(poll_interval_seconds)

            except Exception as e:
                print(f"[!] Attempt {attempts}: Error - {e}")
                time.sleep(poll_interval_seconds)

    def deploy_bwce_app(self, dataplane_id, dataplane_name, app_config):
        """
        Deploy BWCE application

        Args:
            dataplane_id: Dataplane ID
            dataplane_name: Dataplane name
            app_config: Application configuration dict

        Returns:
            dict: Deployment result with success status, build_id, and error
        """
        try:
            from deploy_rest_api import RestApiDeployer

            deployer = RestApiDeployer(self.session, self.auth.host_idm)

            # Extract namespace from config
            namespace = app_config.get('namespace', 'mydp-ns')
            capability_id = app_config.get('capability_id')

            if not capability_id:
                return {
                    "success": False,
                    "error": "No capability_id provided"
                }

            result = deployer.deploy_bwce_app(
                dataplane_id=dataplane_id,
                capability_id=capability_id,
                namespace=namespace,
                app_config=app_config
            )

            return result

        except Exception as e:
            print(f"[!] BWCE Deployment Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def deploy_flogo_app(self, dataplane_id, dataplane_name, app_config):
        """
        Deploy Flogo application

        Args:
            dataplane_id: Dataplane ID
            dataplane_name: Dataplane name
            app_config: Application configuration dict

        Returns:
            dict: Deployment result with success status, build_id, and error
        """
        try:
            from deploy_rest_api import RestApiDeployer

            deployer = RestApiDeployer(self.session, self.auth.host_idm)

            # Extract namespace from config
            namespace = app_config.get('namespace', 'mydp-ns')
            capability_id = app_config.get('capability_id')

            if not capability_id:
                return {
                    "success": False,
                    "error": "No capability_id provided"
                }

            result = deployer.deploy_flogo_app(
                dataplane_id=dataplane_id,
                capability_id=capability_id,
                namespace=namespace,
                app_config=app_config
            )

            return result

        except Exception as e:
            print(f"[!] Flogo Deployment Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def link_activation_server_to_dataplane(self, dataplane_id, activation_server_resource_id):
        """
        Link a global activation server to a specific dataplane.
        This should be called after dataplane registration and before capability provisioning.

        Args:
            dataplane_id: The dataplane ID
            activation_server_resource_id: The resource instance ID of the activation server

        Returns:
            dict: Result with success status and message
        """
        try:
            url = f"{self.auth.host_idm}/cp/api/v1/data-planes/{dataplane_id}/resource-association"

            payload = {
                "resource-instance-id": activation_server_resource_id,
                "resource-type": "ACTIVATION_SERVER",
                "operation": "link",
                "scope": "SUBSCRIPTION",
                "licenseType": "TIBCO_ACTIVATION_SERVICE"
            }

            print(f"[*] Linking activation server to dataplane: {dataplane_id}")
            print(f"    Activation Server Resource ID: {activation_server_resource_id}")

            resp = self.session.put(url, json=payload)

            if resp.status_code in [200, 201]:
                result = resp.json()
                print(f"[+] Activation server linked successfully to dataplane")
                return {
                    "success": True,
                    "message": result.get('response', {}).get('message', 'Linked successfully')
                }
            else:
                print(f"[!] Failed to link activation server. Status: {resp.status_code}")
                print(f"[!] Response: {resp.text}")
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}"
                }

        except Exception as e:
            print(f"[!] Error linking activation server: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def scale_bwce_app(self, dataplane_id, capability_instance_id, app_id, replica_count, namespace="mydp-ns"):
        """
        Scale (start/stop) a BWCE application.

        Args:
            dataplane_id: The dataplane ID
            capability_instance_id: The BWCE capability instance ID
            app_id: The application ID
            replica_count: Number of replicas (0 to stop, 1+ to start)
            namespace: Kubernetes namespace (default: mydp-ns)

        Returns:
            dict: Result with success status
        """
        try:
            url = f"{self.auth.host_idm}/cp/v1/data-planes/{dataplane_id}/dp-resource"

            payload = {
                "path": f"/tibco/agent/integration/{capability_instance_id}/bwprovisioner/private/v1/dp/bw/apps/{app_id}/scale?count={replica_count}&namespace={namespace}",
                "dataPlaneId": dataplane_id,
                "capabilityInstanceId": capability_instance_id,
                "method": "PUT"
            }

            action = "Starting" if replica_count > 0 else "Stopping"
            print(f"[*] {action} BWCE application: {app_id}")
            print(f"    Replica count: {replica_count}")

            resp = self.session.put(url, json=payload, params={"capability_instance_id": capability_instance_id})

            if resp.status_code in [200, 202]:
                result = resp.json()
                print(f"[+] BWCE application scale request accepted")
                return {
                    "success": True,
                    "app_id": result.get('appId', app_id),
                    "status": result.get('status'),
                    "message": result.get('message')
                }
            else:
                print(f"[!] Failed to scale BWCE app. Status: {resp.status_code}")
                print(f"[!] Response: {resp.text}")
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}"
                }

        except Exception as e:
            print(f"[!] Error scaling BWCE app: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def scale_flogo_app(self, dataplane_id, capability_instance_id, app_id, replica_count, namespace="mydp-ns"):
        """
        Scale (start/stop) a Flogo application.

        Args:
            dataplane_id: The dataplane ID
            capability_instance_id: The Flogo capability instance ID
            app_id: The application ID
            replica_count: Number of replicas (0 to stop, 1+ to start)
            namespace: Kubernetes namespace (default: mydp-ns)

        Returns:
            dict: Result with success status
        """
        try:
            url = f"{self.auth.host_idm}/cp/v1/data-planes/{dataplane_id}/dp-resource"

            payload = {
                "path": f"/tibco/agent/integration/{capability_instance_id}/flogoprovisioner/v1/dp/flogo/apps/{app_id}/scale?count={replica_count}&namespace={namespace}",
                "dataPlaneId": dataplane_id,
                "capabilityInstanceId": capability_instance_id,
                "method": "PUT"
            }

            action = "Starting" if replica_count > 0 else "Stopping"
            print(f"[*] {action} Flogo application: {app_id}")
            print(f"    Replica count: {replica_count}")

            resp = self.session.put(url, json=payload, params={"capability_instance_id": capability_instance_id})

            if resp.status_code in [200, 202]:
                result = resp.json()
                print(f"[+] Flogo application scale request accepted")
                return {
                    "success": True,
                    "app_id": result.get('appId', app_id),
                    "status": result.get('status'),
                    "message": result.get('message')
                }
            else:
                print(f"[!] Failed to scale Flogo app. Status: {resp.status_code}")
                print(f"[!] Response: {resp.text}")
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}: {resp.text}"
                }

        except Exception as e:
            print(f"[!] Error scaling Flogo app: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def link_activation_server_to_dataplane(self, dataplane_id, activation_server_resource_id):
        """
        Link activation server to a specific dataplane.
        This should be called for each registered dataplane before provisioning capabilities.

        Args:
            dataplane_id: Dataplane ID
            activation_server_resource_id: Resource instance ID of the activation server

        Returns:
            dict: Result with success status
        """
        try:
            url = f"{self.auth.host_idm}/cp/api/v1/data-planes/{dataplane_id}/resource-association"

            payload = {
                "resource-instance-id": activation_server_resource_id,
                "resource-type": "ACTIVATION_SERVER",
                "operation": "link",
                "scope": "SUBSCRIPTION",
                "licenseType": "TIBCO_ACTIVATION_SERVICE"
            }

            headers = self.get_api_headers()

            print(f"[*] Linking activation server to dataplane...")
            print(f"    Dataplane ID: {dataplane_id}")
            print(f"    Activation Server ID: {activation_server_resource_id}")

            resp = self.session.put(url, json=payload, headers=headers, timeout=30)

            if resp.status_code in [200, 201]:
                result = resp.json()
                message = result.get('response', {}).get('message', 'Linked successfully')
                print(f"[+] {message}")
                return {
                    "success": True,
                    "message": message
                }
            else:
                print(f"[!] Failed to link activation server. Status: {resp.status_code}")
                print(f"[!] Response: {resp.text}")
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}"
                }

        except Exception as e:
            print(f"[!] Error linking activation server: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def use_global_activation_server_for_dataplanes(self, dataplane_ids, activation_server_resource_id):
        """
        Link global activation server to multiple dataplanes.
        This ensures all dataplanes can use the centralized activation server for licensing.

        Args:
            dataplane_ids: List of dataplane IDs
            activation_server_resource_id: Resource instance ID of the activation server

        Returns:
            dict: Summary of linking results
        """
        print(f"\n{'='*60}")
        print(f"[STEP] Link Activation Server to Dataplanes")
        print(f"{'='*60}")
        print(f"[*] Linking activation server to {len(dataplane_ids)} dataplane(s)...")

        results = {
            "total": len(dataplane_ids),
            "successful": 0,
            "failed": 0,
            "details": []
        }

        for dataplane_id in dataplane_ids:
            result = self.link_activation_server_to_dataplane(dataplane_id, activation_server_resource_id)

            if result.get('success'):
                results["successful"] += 1
                results["details"].append({
                    "dataplane_id": dataplane_id,
                    "status": "success"
                })
            else:
                results["failed"] += 1
                results["details"].append({
                    "dataplane_id": dataplane_id,
                    "status": "failed",
                    "error": result.get('error')
                })

        print(f"\n[*] Activation Server Linking Summary:")
        print(f"    Total: {results['total']}")
        print(f"    Successful: {results['successful']}")
        print(f"    Failed: {results['failed']}")

        if results["failed"] > 0:
            print(f"\n[!] Failed dataplanes:")
            for detail in results["details"]:
                if detail["status"] == "failed":
                    print(f"    - {detail['dataplane_id']}: {detail.get('error', 'Unknown error')}")

        return results

    def start_bwce_application(self, dataplane_id, capability_id, app_id, namespace="mydp-ns", replicas=1):
        """
        Start (scale up) a BWCE application.

        Args:
            dataplane_id: Dataplane ID
            capability_id: BWCE capability instance ID
            app_id: Application ID
            namespace: Kubernetes namespace (default: mydp-ns)
            replicas: Number of replicas to scale to (default: 1)

        Returns:
            dict: Result with success status and message
        """
        try:
            url = f"{self.auth.host_idm}/cp/v1/data-planes/{dataplane_id}/dp-resource"

            params = {
                'capability_instance_id': capability_id
            }

            # Build the path for scaling
            path = f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/apps/{app_id}/scale"
            path += f"?count={replicas}&namespace={namespace}"

            payload = {
                "path": path,
                "dataPlaneId": dataplane_id,
                "capabilityInstanceId": capability_id,
                "method": "PUT"
            }

            print(f"[*] Starting BWCE application...")
            print(f"    App ID: {app_id}")
            print(f"    Replicas: {replicas}")

            headers = self.get_api_headers()
            resp = self.session.put(url, json=payload, headers=headers, params=params)

            if resp.status_code in [200, 202]:
                result = resp.json()
                print(f"[+] Application start request accepted")
                return {
                    "success": True,
                    "message": result.get('message', 'Application started successfully'),
                    "status": result.get('status'),
                    "code": result.get('code')
                }
            else:
                error_msg = f"HTTP {resp.status_code}"
                try:
                    error_data = resp.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    error_msg = resp.text[:200]

                print(f"[!] Failed to start application. Status: {resp.status_code}")
                print(f"    Response: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }

        except Exception as e:
            print(f"[!] Error starting BWCE application: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def start_flogo_application(self, dataplane_id, capability_id, app_id, namespace="mydp-ns", replicas=1):
        """
        Start (scale up) a Flogo application.

        Args:
            dataplane_id: Dataplane ID
            capability_id: Flogo capability instance ID
            app_id: Application ID
            namespace: Kubernetes namespace (default: mydp-ns)
            replicas: Number of replicas to scale to (default: 1)

        Returns:
            dict: Result with success status and message
        """
        try:
            url = f"{self.auth.host_idm}/cp/v1/data-planes/{dataplane_id}/dp-resource"

            params = {
                'capability_instance_id': capability_id
            }

            # Build the path for scaling
            path = f"/tibco/agent/integration/{capability_id}/flogoprovisioner/v1/dp/flogo/apps/{app_id}/scale"
            path += f"?count={replicas}&namespace={namespace}"

            payload = {
                "path": path,
                "dataPlaneId": dataplane_id,
                "capabilityInstanceId": capability_id,
                "method": "PUT"
            }

            print(f"[*] Starting Flogo application...")
            print(f"    App ID: {app_id}")
            print(f"    Replicas: {replicas}")

            headers = self.get_api_headers()
            resp = self.session.put(url, json=payload, headers=headers, params=params)

            if resp.status_code in [200, 202]:
                result = resp.json()
                print(f"[+] Application start request accepted")
                return {
                    "success": True,
                    "message": result.get('message', 'Application started successfully'),
                    "status": result.get('status'),
                    "code": result.get('code')
                }
            else:
                error_msg = f"HTTP {resp.status_code}"
                try:
                    error_data = resp.json()
                    error_msg = error_data.get('message', error_msg)
                except:
                    error_msg = resp.text[:200]

                print(f"[!] Failed to start application. Status: {resp.status_code}")
                print(f"    Response: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }

        except Exception as e:
            print(f"[!] Error starting Flogo application: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

