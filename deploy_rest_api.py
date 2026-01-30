"""
REST API-based deployment implementation
Based on JavaScript files: bwceAppApiEndpoint.js and flogoAppApiEndpoint.js
"""

import os
import time
import json
import re
import requests


class RestApiDeployer:
    """
    Deploy BWCE and Flogo applications using REST API
    Matches the JavaScript implementation exactly
    """

    @staticmethod
    def sanitize_app_name(app_name):
        """
        Sanitize app name for BWCE deployment.
        BWCE requirement: only lowercase alphanumeric characters & '-' are allowed

        Example: "BWCETimerLog" -> "bwcetimerlog"
                 "My_App_Name" -> "my-app-name"
        """
        # Convert to lowercase
        name = app_name.lower()
        # Replace underscores with hyphens
        name = name.replace('_', '-')
        # Remove any characters that are not alphanumeric or hyphen
        name = re.sub(r'[^a-z0-9-]', '', name)
        # Remove leading/trailing hyphens
        name = name.strip('-')
        # Replace multiple consecutive hyphens with single hyphen
        name = re.sub(r'-+', '-', name)
        return name

    def __init__(self, session, tenant_host):
        """
        Initialize with authenticated session

        Args:
            session: requests.Session with authentication cookies
            tenant_host: Tenant URL (e.g., https://tenant.cp1-my.localhost.dataplanes.pro)
        """
        self.session = session
        self.tenant_host = tenant_host.rstrip('/')

    def deploy_bwce_app(self, dataplane_id, capability_id, namespace, app_config):
        """
        Deploy BWCE application using REST API

        Flow (from bwceAppApiEndpoint.js):
        1. store() - Upload .ear file to CP filesystem
        2. createBuild() - Create build
        3. Poll build status
        4. deployApp() - Deploy the application

        Args:
            dataplane_id: Dataplane ID
            capability_id: BWCE capability instance ID
            namespace: Kubernetes namespace
            app_config: App configuration dict

        Returns:
            dict: Deployment result
        """
        print(f"\n[*] Deploying BWCE application via REST API")
        print(f"    App: {app_config.get('app_name')}")
        print(f"    Dataplane ID: {dataplane_id}")
        print(f"    Capability ID: {capability_id}")

        # Get app file
        app_folder = app_config.get('app_folder', 'apps_to_deploy')
        app_file_name = app_config.get('app_file_name')
        app_name = app_config.get('app_name')

        if not app_file_name:
            return {"success": False, "error": "No app_file_name provided"}

        app_file_path = os.path.join(app_folder, 'bwce', app_file_name)
        app_file_path = os.path.abspath(app_file_path)

        if not os.path.exists(app_file_path):
            return {"success": False, "error": f"File not found: {app_file_path}"}

        print(f"    App file: {app_file_path}")

        try:
            # Step 1: Upload file to CP filesystem (store)
            print(f"\n[*] Step 1: Uploading file to CP filesystem...")
            file_id = self._store_bwce_file(app_file_path)
            if not file_id:
                return {"success": False, "error": "File upload failed"}

            print(f"[+] File uploaded successfully. File ID: {file_id}")

            # Step 2: Check if BWCE version is provisioned, provision if needed
            print(f"\n[*] Step 2: Checking BWCE version provisioning...")
            provisioned_versions = self._list_provisioned_bwce_versions(dataplane_id, capability_id)

            if not provisioned_versions:
                print(f"[!] No BWCE versions provisioned. Provisioning latest version...")
                if not self._provision_latest_bwce_version(dataplane_id, capability_id):
                    return {"success": False, "error": "Failed to provision BWCE version"}
                # Refresh the list after provisioning
                provisioned_versions = self._list_provisioned_bwce_versions(dataplane_id, capability_id)

            # Get the latest provisioned version
            bwce_version = provisioned_versions[0]['version']
            base_image_tag = provisioned_versions[0]['baseImageTag']

            print(f"[+] Using BWCE Version: {bwce_version}")
            print(f"[+] Using Base Image Tag: {base_image_tag}")

            # Step 3: Create build
            print(f"\n[*] Step 3: Creating build...")
            build_result = self._create_bwce_build(
                dataplane_id,
                capability_id,
                file_id,
                app_name,
                bwce_version,
                base_image_tag
            )

            if not build_result.get('success'):
                return build_result

            build_id = build_result.get('build_id')
            print(f"[+] Build created successfully. Build ID: {build_id}")

            # NOTE: BWCE does NOT wait for build completion (confirmed from HAR and JavaScript)
            # The JavaScript code (bwceAppUtils.js line 76-81) immediately deploys after build
            # The HAR file shows: Upload → Build → Deploy (NO status polling)
            # The build happens asynchronously and deployment handles it internally

            # Step 4: Deploy application immediately (no build wait)
            print(f"\n[*] Step 4: Deploying application...")

            # IMPORTANT: BWCE requires lowercase app names (alphanumeric + '-' only)
            app_name_sanitized = self.sanitize_app_name(app_name)
            if app_name_sanitized != app_name:
                print(f"[*] App name sanitized: '{app_name}' -> '{app_name_sanitized}'")

            deploy_result = self._deploy_bwce_app(
                dataplane_id,
                capability_id,
                namespace,
                build_id,
                app_name_sanitized
            )

            if deploy_result.get('success'):
                print(f"[+] Application deployed successfully!")
                return {
                    "success": True,
                    "app_name": app_name_sanitized,
                    "build_id": build_id,
                    "app_id": deploy_result.get('app_id'),
                    "dataplane_id": dataplane_id,
                    "capability_id": capability_id,
                    "namespace": namespace
                }
            else:
                return deploy_result

        except Exception as e:
            print(f"[!] Deployment error: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _store_bwce_file(self, file_path):
        """
        Upload BWCE .ear file to CP filesystem
        Matches: async store(data) in bwceAppApiEndpoint.js
        """
        url = f"{self.tenant_host}/cp/bwce/v1/files/store"

        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'application/octet-stream')
            }

            print(f"[DEBUG] Upload URL: {url}")

            resp = self.session.post(
                url,
                files=files,
                verify=False
            )

            print(f"[DEBUG] Upload status: {resp.status_code}")

            if resp.status_code in [200, 201]:
                result = resp.json()
                print(f"[DEBUG] Upload response: {json.dumps(result, indent=2)}")
                # Response contains 'fileName' which is the file ID/path
                file_id = result.get('fileName') or result.get('fileId') or result.get('id')
                return file_id
            else:
                print(f"[!] Upload failed. Status: {resp.status_code}")
                print(f"[!] Response: {resp.text}")
                return None

    def _list_provisioned_bwce_versions(self, dataplane_id, capability_id):
        """
        List provisioned BWCE versions on the dataplane
        Matches: async listBwceVersion(dpId,capabilityId) in bwceAppApiEndpoint.js
        """
        path = f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/buildtype"
        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'sortBy': 'buildtypeTag',
            'orderBy': 'desc',  # Get latest first
            'filterKey': '',
            'filterValue': '',
            'path': path
        }

        resp = self.session.get(url, params=params, verify=False)

        if resp.status_code == 200:
            result = resp.json()
            total = result.get('totalBuildtypes', 0)

            if total == 0:
                print(f"[!] No BWCE versions provisioned yet")
                return []

            buildtypes = result.get('buildtypeCatalog', [])
            versions = []

            for bt in buildtypes:
                version = bt.get('buildtypeTag')
                base_images = bt.get('baseImages', [])
                if base_images:
                    base_image_tag = base_images[0].get('imageTag')
                    versions.append({'version': version, 'baseImageTag': base_image_tag})

            print(f"[+] Found {len(versions)} provisioned BWCE version(s)")
            return versions
        else:
            print(f"[!] Failed to list BWCE versions. Status: {resp.status_code}")
            return []

    def _list_available_bwce_versions(self):
        """
        List available BWCE versions from catalog
        Matches: async listBwceBuildTypes(data) in bwceAppApiEndpoint.js
        """
        url = f"{self.tenant_host}/cp/bwce/v1/buildTypes"

        resp = self.session.get(url, verify=False)

        if resp.status_code == 200:
            result = resp.json()
            versions = result.get('data', [])
            print(f"[+] Found {len(versions)} available BWCE version(s) in catalog")
            return versions
        else:
            print(f"[!] Failed to list available BWCE versions. Status: {resp.status_code}")
            return []

    def provision_bwce_buildtype(self, dataplane_id, capability_id, version="6.12.0-HF1"):
        """
        Provision BWCE buildtype (runtime templates and deployment files).
        MUST be called before deploying any BWCE applications.
        Based on HAR file analysis - uses exact payload structure.
        """
        import random
        import string

        print(f"\n[*] Provisioning BWCE buildtype {version}...")

        try:
            # Generate random event ID (like the HAR shows)
            random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=31))
            event_id = f"bwce_{random_str}"

            # Build the payload exactly as in HAR file
            payload = {
                "dataPlaneId": dataplane_id,
                "path": f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/buildtype/{version}",
                "eventId": event_id,
                "queryParams": {
                    "capability_instance_id": capability_id
                },
                "payload": {
                    "tags": [],
                    "filesList": [
                        {"fileName": "bwapp-deploy-template.yaml", "downloadURL": f"/bwce/buildtypes/{version}/bwapp-deploy-template.yaml"},
                        {"fileName": "bwapp-svc-template.yaml", "downloadURL": f"/bwce/buildtypes/{version}/bwapp-svc-template.yaml"},
                        {"fileName": "metadata.json", "downloadURL": f"/bwce/buildtypes/{version}/metadata.json"}
                    ]
                }
            }

            # Use the same URL structure as HAR
            url = f"{self.tenant_host}/cp/bwce/v1/data-planes/{dataplane_id}/dp-resource"

            resp = self.session.post(
                url,
                params=payload['queryParams'],
                json=payload,
                headers={'Content-Type': 'application/json'},
                verify=False
            )

            if resp.status_code == 200:
                response_data = resp.json()
                if response_data.get('status') == 'success':
                    print(f"[+] BWCE buildtype {version} provisioned successfully!")
                    return {"success": True, "version": version}
                else:
                    return {"success": False, "error": response_data.get('message')}
            else:
                print(f"[!] BWCE buildtype provisioning failed. Status: {resp.status_code}")
                print(f"[!] Response: {resp.text}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}

        except Exception as e:
            print(f"[!] Exception during BWCE buildtype provisioning: {e}")
            return {"success": False, "error": str(e)}

    def _provision_latest_bwce_version(self, dataplane_id, capability_id):
        """
        Provision the latest BWCE version/plugin
        Matches: async provisionBwcePlugin(dpId,capabilityId,payload) in bwceAppApiEndpoint.js
        Based on provisionLatestBwcePlugin in bwceAppUtils.js
        """
        # Get available versions from catalog
        available = self._list_available_bwce_versions()

        if not available:
            print(f"[!] No BWCE versions available in catalog")
            return False

        # Sort and get latest version
        versions = [v['version'] for v in available]
        latest_version = sorted(versions, reverse=True)[0]

        print(f"[*] Provisioning BWCE version: {latest_version}")

        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'capability_instance_id': capability_id
        }

        # Payload structure from bwceAppUtils.js
        payload = {
            "dataPlaneId": dataplane_id,
            "path": f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/buildtype",
            "queryParams": {
                "capability_instance_id": capability_id
            },
            "payload": {
                "buildTypeVersion": latest_version
            },
            "eventId": f"bwce_provision_{int(time.time())}"
        }

        resp = self.session.post(url, json=payload, params=params, verify=False)

        if resp.status_code in [200, 201, 202]:
            print(f"[+] BWCE version {latest_version} provisioned successfully")
            # Wait a bit for provisioning to complete
            time.sleep(10)
            return True
        else:
            print(f"[!] Failed to provision BWCE version. Status: {resp.status_code}")
            print(f"[!] Response: {resp.text}")
            return False

    def _get_bwce_capability_info(self, dataplane_id, capability_id):
        """
        Get BWCE capability info (version, base image tag)
        Matches: async getCapabilityInfo(dpId,capabilityInstanceId) in bwceAppApiEndpoint.js
        """
        # /tp-cp-ws/v1/data-planes/{dpId}/dp-resource?path=/tibco/agent/integration/{capabilityInstanceId}/bwprovisioner/private/v1/dp/bw/info
        path = f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/info"
        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

        params = {'path': path}

        resp = self.session.get(url, params=params, verify=False)

        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"[!] Could not get BWCE info. Using defaults.")
            return {}

    def _create_bwce_build(self, dataplane_id, capability_id, file_id, app_name, bwce_version, base_image_tag):
        """
        Create BWCE application build
        Matches: async createBuild(dpId,capabilityInstanceId,payload) in bwceAppApiEndpoint.js

        Uses the same wrapper structure as Flogo (confirmed from HAR file)
        IMPORTANT: Uses "filePath" not "fileId" (confirmed from bwceHelper.js)
        HAR Analysis: Includes autoProvision=false parameter
        """
        url = f"{self.tenant_host}/cp/bwce/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'baseversion': bwce_version,
            'baseimagetag': base_image_tag,
            'capability_instance_id': capability_id,
            'autoProvision': 'false'  # NEW: From HAR analysis
        }

        # The body has a special wrapper structure (same as Flogo)
        payload = {
            "dataPlaneId": dataplane_id,
            "path": f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/builds",
            "queryParams": {
                "baseversion": bwce_version,
                "baseimagetag": base_image_tag,
                "capability_instance_id": capability_id,
                "autoProvision": "false"  # NEW: From HAR analysis
            },
            "payload": {
                "dependencies": [],  # Empty for now
                "filePath": file_id,  # CHANGED from fileId to filePath
                "tags": [],
                "buildName": app_name if app_name else ""  # Can be empty string
            },
            "eventId": f"bwce_build_{int(time.time())}"
        }

        print(f"[DEBUG] BWCE Build URL: {url}")
        print(f"[DEBUG] BWCE Build params: {params}")
        print(f"[DEBUG] BWCE Build payload:")
        print(json.dumps(payload, indent=2))
        print(f"[DEBUG] File path being used: {file_id}")

        resp = self.session.post(url, json=payload, params=params, verify=False)

        print(f"[DEBUG] BWCE Build status: {resp.status_code}")

        if resp.status_code in [200, 201, 202]:  # 202 = Accepted (async operation)
            try:
                result = resp.json()
                print(f"[DEBUG] BWCE Build response: {json.dumps(result, indent=2)}")
                build_id = result.get('buildId') or result.get('id')
                if build_id:
                    return {"success": True, "build_id": build_id}
                else:
                    print(f"[!] Build ID not found in response")
                    return {"success": False, "error": "Build ID not in response"}
            except Exception as e:
                print(f"[!] Error parsing build response: {e}")
                print(f"[!] Raw response: {resp.text}")
                return {"success": False, "error": str(e)}
        else:
            print(f"[!] BWCE Build creation failed. Status: {resp.status_code}")
            try:
                error_detail = resp.json()
                print(f"[!] Error response: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"[!] Response: {resp.text}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}

    def _wait_for_bwce_build(self, dataplane_id, capability_id, build_id, max_wait=300, poll_interval=10):
        """
        Poll build status until complete
        """
        # /tp-cp-ws/v1/data-planes/{dpId}/dp-resource?path=/tibco/agent/integration/{capId}/bwprovisioner/private/v1/dp/bw/builds/{buildId}/status
        path = f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/builds/{build_id}/status"
        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

        params = {'path': path}

        start_time = time.time()
        attempts = 0

        while time.time() - start_time < max_wait:
            attempts += 1
            print(f"[*] Checking build status (attempt {attempts})...")

            resp = self.session.get(url, params=params, verify=False)

            print(f"[DEBUG] Status check response code: {resp.status_code}")

            if resp.status_code == 200:
                try:
                    result = resp.json()
                    print(f"[DEBUG] Status response: {json.dumps(result, indent=2)}")
                    status = result.get('status', '').lower()

                    print(f"    Build status: {status}")

                    if status == 'success' or status == 'completed':
                        return True
                    elif status == 'failed' or status == 'error':
                        print(f"[!] Build failed: {result.get('message')}")
                        return False
                except Exception as e:
                    print(f"[!] Error parsing status response: {e}")
                    print(f"[!] Raw response: {resp.text}")
            else:
                print(f"[!] Status check failed with code {resp.status_code}")
                print(f"[!] Response: {resp.text[:200]}")

            time.sleep(poll_interval)

        print(f"[!] Build timeout after {max_wait} seconds")
        return False

    def _deploy_bwce_app(self, dataplane_id, capability_id, namespace, build_id, app_name):
        """
        Deploy BWCE application
        Matches: async deployApp(dpId,capabilityInstanceId,namespace,payload) in bwceAppApiEndpoint.js
        Based on bwceHelper.js createDeployPayload method

        Uses wrapper structure like build creation
        IMPORTANT: Requires eula: true (confirmed from bwceHelper.js line 115)
        HAR Analysis: Uses /cp/bwce/v1/ URL and replicas=0
        """
        url = f"{self.tenant_host}/cp/bwce/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'namespace': namespace,
            'capability_instance_id': capability_id
        }

        # Deploy payload structure from HAR analysis and bwceHelper.js
        payload = {
            "dataPlaneId": dataplane_id,
            "path": f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/deploy",
            "queryParams": {
                "namespace": namespace,
                "capability_instance_id": capability_id
            },
            "payload": {
                "appId": "",  # Empty for new deployment
                "buildId": build_id,
                "eula": True,  # REQUIRED: Accept End User License Agreement
                "appName": app_name,
                "tags": [],
                "profile": "default.substvar",  # Default profile
                "replicas": 0,  # HAR shows 0, not 1
                "enableExecutionHistory": False,
                "enableServiceMesh": False,
                "enableAutoscaling": False,
                "resourceLimits": {
                    "limits": {
                        "cpu": "1",
                        "memory": "4096Mi"
                    },
                    "requests": {
                        "cpu": "250m",
                        "memory": "1024Mi"
                    }
                }
            },
            "eventId": f"bwce_deploy_{int(time.time())}"
        }

        print(f"[DEBUG] BWCE Deploy URL: {url}")
        print(f"[DEBUG] BWCE Deploy params: {params}")
        print(f"[DEBUG] BWCE Deploy payload: {json.dumps(payload, indent=2)}")

        resp = self.session.post(url, json=payload, params=params, verify=False)

        print(f"[DEBUG] BWCE Deploy status: {resp.status_code}")

        if resp.status_code in [200, 201, 202]:
            try:
                result = resp.json()
                print(f"[DEBUG] BWCE Deploy response: {json.dumps(result, indent=2)}")
                return {"success": True, "app_id": result.get('appId') or result.get('id')}
            except:
                # Response might not be JSON
                print(f"[+] Deployment accepted (non-JSON response)")
                return {"success": True, "app_id": None}
        else:
            print(f"[!] BWCE Deploy failed. Status: {resp.status_code}")
            print(f"[!] Response: {resp.text}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}

    def provision_flogo_buildtype(self, dataplane_id, capability_id, version="2.26.1-b357"):
        """
        Provision Flogo buildtype/runtime templates.
        MUST be called before deploying any Flogo applications.
        """
        import time
        import random
        import string

        print(f"\n[*] Provisioning Flogo buildtype {version}...")

        try:
            # Generate random event ID
            random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=31))
            event_id = f"flogo_{random_str}"

            # Build the payload exactly as in HAR file
            payload = {
                "dataPlaneId": dataplane_id,
                "path": f"/tibco/agent/integration/{capability_id}/flogoprovisioner/v1/dp/flogo/buildtype/{version}",
                "queryParams": {
                    "capability_instance_id": capability_id
                },
                "payload": {
                    "tags": [],
                    "filesList": [
                        {"fileName": "go.mod", "downloadURL": f"/flogo/buildtypes/{version}/go.mod"},
                        {"fileName": "go.sum", "downloadURL": f"/flogo/buildtypes/{version}/go.sum"},
                        {"fileName": "metadata.json", "downloadURL": f"/flogo/buildtypes/{version}/metadata.json"},
                        {"fileName": "tpcl.zip", "downloadURL": f"/flogo/buildtypes/{version}/tpcl.zip"},
                        {"fileName": "version.txt", "downloadURL": f"/flogo/buildtypes/{version}/version.txt"},
                        {"fileName": "wi-contrib.zip", "downloadURL": f"/flogo/buildtypes/{version}/wi-contrib.zip"}
                    ]
                },
                "eventId": event_id
            }

            url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

            resp = self.session.post(
                url,
                params=payload['queryParams'],
                json=payload,
                headers={'Content-Type': 'application/json'},
                verify=False
            )

            if resp.status_code == 200:
                response_data = resp.json()
                if response_data.get('status') == 'success':
                    print(f"[+] Flogo buildtype {version} provisioned successfully!")
                    return {"success": True, "version": version}
                else:
                    return {"success": False, "error": response_data.get('message')}
            else:
                print(f"[!] Flogo buildtype provisioning failed. Status: {resp.status_code}")
                return {"success": False, "error": f"HTTP {resp.status_code}"}

        except Exception as e:
            print(f"[!] Exception during Flogo buildtype provisioning: {e}")
            return {"success": False, "error": str(e)}

    def provision_flogo_connectors(self, dataplane_id, flogo_capability_id, connectors=None):
        """
        Provision Flogo connectors (e.g., General connector).
        Must be done AFTER buildtype provisioning and before deploying applications.

        Based on the HAR file, connectors are provisioned via artifactmanager, not flogoprovisioner.
        The path uses INTEGRATIONCORE capability ID, but query param uses FLOGO capability ID.
        """
        import time

        if connectors is None:
            connectors = ["General"]

        print(f"\n[*] Provisioning Flogo connectors: {', '.join(connectors)}...")

        try:
            # Step 1: Get INTEGRATIONCORE capability ID (for artifactmanager)
            # Connectors are managed by artifactmanager, not flogoprovisioner
            integrationcore_cap_id = self._get_integrationcore_capability_id(dataplane_id)
            if not integrationcore_cap_id:
                print(f"[!] Could not find INTEGRATIONCORE capability")
                return {"success": False, "error": "INTEGRATIONCORE capability not found"}

            print(f"[+] Found INTEGRATIONCORE capability ID: {integrationcore_cap_id}")

            # Step 2: Build artifacts payload
            # Based on HAR: /tibco/agent/integration/{INTEGRATIONCORE_ID}/artifactmanager/v1/artifacts
            # The payload uses exact format from flogo-version-har
            artifacts = []
            for conn_name in connectors:
                # Default connector paths and versions
                if conn_name == "General":
                    artifact = {
                        "name": "General",
                        "path": "/flogo-contribution/tp-flogo-connector-general/1.6.12-b03",
                        "targetPath": f"{dataplane_id}/tibco/flogo/connectors",
                        "version": "1.6.12-b03",
                        "files": ["Dockerfile", "connector.zip", "contribution.json"],
                        "catalog": {
                            "name": "General",
                            "id": "General",
                            "version": "1.6.12-b03",
                            "displayName": "1.6.12"
                        }
                    }
                    artifacts.append(artifact)

            if not artifacts:
                print(f"[!] No artifacts to provision")
                return {"success": False, "error": "No valid connectors"}

            # Step 3: Provision via artifactmanager
            # URL: /tp-cp-ws/v1/data-planes/{dp_id}/dp-resource?capability_instance_id={flogo_cap_id}
            provision_url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

            # The payload structure from flogo-version-har
            payload = {
                "dataPlaneId": dataplane_id,
                "path": f"/tibco/agent/integration/{integrationcore_cap_id}/artifactmanager/v1/artifacts",
                "queryParams": {
                    "capability_instance_id": flogo_capability_id
                },
                "payload": {
                    "connection": {
                        "path": "/files",
                        "token": "",
                        "basicauth": ""
                    },
                    "artifacts": artifacts
                },
                "eventId": f"flogo_{self._generate_random_id()}"
            }

            print(f"[DEBUG] Provision URL: {provision_url}")
            print(f"[DEBUG] INTEGRATIONCORE Cap ID: {integrationcore_cap_id}")
            print(f"[DEBUG] Flogo Cap ID (query param): {flogo_capability_id}")
            print(f"[DEBUG] Provisioning {len(artifacts)} connector(s)...")

            resp = self.session.post(
                provision_url,
                params={"capability_instance_id": flogo_capability_id},
                json=payload,
                headers={'Content-Type': 'application/json'},
                verify=False
            )

            print(f"[DEBUG] Connector provision status: {resp.status_code}")

            if resp.status_code in [200, 201, 202]:
                try:
                    resp_data = resp.json()
                    print(f"[DEBUG] Response: {resp_data}")
                    print(f"[+] Connectors provisioned successfully!")
                except:
                    print(f"[+] Connectors provisioned successfully!")
                return {"success": True, "connectors": artifacts}
            else:
                print(f"[!] Connector provisioning failed: {resp.status_code}")
                print(f"[!] Response: {resp.text}")
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}"}

        except Exception as e:
            print(f"[!] Exception during connector provisioning: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _get_integrationcore_capability_id(self, dataplane_id):
        """Get the INTEGRATIONCORE capability instance ID"""
        try:
            status_url = f"{self.tenant_host}/cp/v1/data-planes/{dataplane_id}/capabilities-status"
            resp = self.session.get(status_url, headers={'Content-Type': 'application/json'}, verify=False)

            if resp.status_code == 200:
                data = resp.json()
                dataplanes = data.get('dataplanes', [])
                for dp in dataplanes:
                    if dp.get('dp_id') == dataplane_id:
                        capabilities = dp.get('capabilities', [])
                        for cap in capabilities:
                            if cap.get('capability') == 'INTEGRATIONCORE':
                                return cap.get('capability_instance_id')
            return None
        except:
            return None

    def _generate_random_id(self):
        """Generate a random ID for event tracking"""
        import random
        import string
        return ''.join(random.choices(string.ascii_letters + string.digits, k=30))

    def deploy_flogo_app(self, dataplane_id, capability_id, namespace, app_config):
        """
        Deploy Flogo application using REST API
        Based on flogoAppApiEndpoint.js
        """
        print(f"\n[*] Deploying Flogo application via REST API")
        print(f"    App: {app_config.get('app_name')}")
        print(f"    Dataplane ID: {dataplane_id}")
        print(f"    Capability ID: {capability_id}")

        # Get app file
        app_folder = app_config.get('app_folder', 'apps_to_deploy')
        app_file_name = app_config.get('app_file_name')
        app_name = app_config.get('app_name')

        if not app_file_name:
            return {"success": False, "error": "No app_file_name provided"}

        app_file_path = os.path.join(app_folder, 'flogo', app_file_name)
        app_file_path = os.path.abspath(app_file_path)

        if not os.path.exists(app_file_path):
            return {"success": False, "error": f"File not found: {app_file_path}"}

        print(f"    App file: {app_file_path}")

        try:
            # Step 1: Upload file
            print(f"\n[*] Step 1: Uploading file to CP filesystem...")
            file_id = self._store_flogo_file(app_file_path)
            if not file_id:
                return {"success": False, "error": "File upload failed"}

            print(f"[+] File uploaded successfully. File ID: {file_id}")

            # Step 2: Get Flogo version
            print(f"\n[*] Step 2: Getting Flogo capability info...")
            flogo_info = self._get_flogo_capability_info(dataplane_id, capability_id)
            flogo_version = flogo_info.get('version', '1.0.0')
            print(f"    Flogo Version: {flogo_version}")

            # Step 3: Create build
            print(f"\n[*] Step 3: Creating build...")
            build_result = self._create_flogo_build(
                dataplane_id,
                capability_id,
                file_id,
                app_name,
                flogo_version
            )

            if not build_result.get('success'):
                return build_result

            build_id = build_result.get('build_id')
            print(f"[+] Build created successfully. Build ID: {build_id}")

            # Step 4: Poll build status
            print(f"\n[*] Step 4: Waiting for build to complete...")
            if not self._wait_for_flogo_build(dataplane_id, capability_id, build_id):
                return {"success": False, "error": "Build failed or timed out"}

            print(f"[+] Build completed successfully!")

            # Step 5: Deploy application
            print(f"\n[*] Step 5: Deploying application...")
            deploy_result = self._deploy_flogo_app_final(
                dataplane_id,
                capability_id,
                namespace,
                build_id,
                app_name
            )

            if deploy_result.get('success'):
                print(f"[+] Application deployed successfully!")
                return {
                    "success": True,
                    "app_name": app_name,
                    "build_id": build_id,
                    "app_id": deploy_result.get('app_id'),
                    "dataplane_id": dataplane_id,
                    "capability_id": capability_id,
                    "namespace": namespace
                }
            else:
                return deploy_result

        except Exception as e:
            print(f"[!] Deployment error: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def _store_flogo_file(self, file_path):
        """
        Upload Flogo .flogo file to CP filesystem
        Matches: async storeFlogoToEFS(data) in flogoAppApiEndpoint.js
        """
        url = f"{self.tenant_host}/cp/flogo/v1/files/store"

        with open(file_path, 'rb') as f:
            files = {
                'file': (os.path.basename(file_path), f, 'application/octet-stream')
            }

            resp = self.session.post(url, files=files, verify=False)

            if resp.status_code in [200, 201]:
                result = resp.json()
                # Response contains 'fileName' which is the file ID/path
                file_id = result.get('fileName') or result.get('fileId') or result.get('id')
                return file_id
            else:
                print(f"[!] Upload failed. Status: {resp.status_code}, Response: {resp.text}")
                return None

    def _get_flogo_capability_info(self, dataplane_id, capability_id):
        """Get Flogo capability info"""
        path = f"/tibco/agent/integration/{capability_id}/flogoprovisioner/v1/dp/flogo/info"
        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"
        params = {'capability_instance_id': capability_id, 'path': path}

        resp = self.session.get(url, params=params, verify=False)

        if resp.status_code == 200:
            return resp.json()
        else:
            return {}

    def _create_flogo_build(self, dataplane_id, capability_id, file_id, app_name, flogo_version):
        """
        Create Flogo build
        Based on actual HAR file: deploy-flogo-app

        The request uses a wrapper structure with dataPlaneId, path, queryParams, and payload
        """
        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'baseversion': flogo_version,
            'capability_instance_id': capability_id
        }

        # The body has a special wrapper structure
        payload = {
            "dataPlaneId": dataplane_id,
            "path": f"/tibco/agent/integration/{capability_id}/flogoprovisioner/v1/dp/flogo/builds",
            "queryParams": {
                "baseversion": flogo_version,
                "capability_instance_id": capability_id
            },
            "payload": {
                "dependencies": [],  # Empty for now, can be populated if needed
                "buildName": app_name,
                "filePath": file_id,
                "tags": []
            },
            "eventId": f"flogo_build_{int(time.time())}"
        }

        print(f"[DEBUG] Flogo build URL: {url}")
        print(f"[DEBUG] Flogo build params: {params}")
        print(f"[DEBUG] Flogo build payload: {json.dumps(payload, indent=2)}")

        resp = self.session.post(url, json=payload, params=params, verify=False)

        print(f"[DEBUG] Flogo build status: {resp.status_code}")

        if resp.status_code in [200, 201, 202]:  # 202 = Accepted (async operation)
            result = resp.json()
            print(f"[DEBUG] Flogo build response: {json.dumps(result, indent=2)}")
            build_id = result.get('buildId') or result.get('id') or result.get('buildName')
            return {"success": True, "build_id": build_id}
        else:
            print(f"[!] Build creation failed. Status: {resp.status_code}, Response: {resp.text}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}

    def _wait_for_flogo_build(self, dataplane_id, capability_id, build_id, max_wait=300, poll_interval=10):
        """Poll Flogo build status"""
        # Use getFlogoBuildStatus endpoint
        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'capability_instance_id': capability_id,
            'path': f"/tibco/agent/integration/{capability_id}/flogoprovisioner/v1/dp/flogo/builds/{build_id}/status"
        }

        start_time = time.time()
        attempts = 0

        while time.time() - start_time < max_wait:
            attempts += 1
            print(f"[*] Checking build status (attempt {attempts})...")

            resp = self.session.get(url, params=params, verify=False)

            if resp.status_code == 200:
                result = resp.json()
                status = result.get('status', '').lower()

                print(f"    Build status: {status}")

                if status == 'success' or status == 'completed':
                    return True
                elif status == 'failed' or status == 'error':
                    print(f"[!] Build failed: {result.get('message')}")
                    return False

            time.sleep(poll_interval)

        print(f"[!] Build timeout after {max_wait} seconds")
        return False

    def _deploy_flogo_app_final(self, dataplane_id, capability_id, namespace, build_id, app_name):
        """
        Deploy Flogo application using wrapper structure
        Path should be /deploy not /apps based on flogoAppApiEndpoint.js

        IMPORTANT: Requires eula: true (lowercase) to accept TIBCO End User Agreement
        Based on flogoHelper.js line 124
        """
        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'namespace': namespace,
            'capability_instance_id': capability_id
        }

        # Deploy payload structure from flogoHelper.js
        payload = {
            "dataPlaneId": dataplane_id,
            "path": f"/tibco/agent/integration/{capability_id}/flogoprovisioner/v1/dp/flogo/deploy",
            "queryParams": {
                "namespace": namespace,
                "capability_instance_id": capability_id
            },
            "payload": {
                "appId": "",  # Empty for new deployment
                "buildId": build_id,
                "eula": True,  # REQUIRED: Accept End User License Agreement (lowercase!)
                "appName": app_name,
                "tags": [],
                "enableServiceMesh": False,
                "resourceLimits": {
                    "limits": {
                        "cpu": "500m",
                        "memory": "1024Mi"
                    },
                    "requests": {
                        "cpu": "250m",
                        "memory": "512Mi"
                    }
                }
            },
            "eventId": f"flogo_deploy_{int(time.time())}"
        }

        print(f"[DEBUG] Flogo Deploy URL: {url}")
        print(f"[DEBUG] Flogo Deploy payload: {json.dumps(payload, indent=2)}")

        resp = self.session.post(url, json=payload, params=params, verify=False)

        print(f"[DEBUG] Flogo Deploy status: {resp.status_code}")

        if resp.status_code in [200, 201, 202]:
            try:
                result = resp.json()
                print(f"[DEBUG] Flogo Deploy response: {json.dumps(result, indent=2)}")
                return {"success": True, "app_id": result.get('appId') or result.get('id')}
            except:
                # Response might not be JSON
                print(f"[+] Deployment accepted (non-JSON response)")
                return {"success": True, "app_id": None}
        else:
            print(f"[!] Flogo Deploy failed. Status: {resp.status_code}, Response: {resp.text}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}


    def scale_bwce_app(self, dataplane_id, capability_id, app_id, namespace, replica_count):
        """
        Scale a BWCE application (start/stop by setting replica count)

        Args:
            dataplane_id: The dataplane ID
            capability_id: The BWCE capability instance ID
            app_id: The application ID to scale
            namespace: Kubernetes namespace
            replica_count: Number of replicas (0 = stop, 1+ = start/scale)

        Returns:
            dict: {"success": bool, "message": str}
        """
        # Based on start-apps-har:
        # PUT to /cp/v1/data-planes/{dp_id}/dp-resource?capability_instance_id={cap_id}
        # Payload: {"path": "/tibco/agent/integration/{cap_id}/bwprovisioner/private/v1/dp/bw/apps/{app_id}/scale?count={count}&namespace={ns}", ...}

        url = f"{self.tenant_host}/cp/v1/data-planes/{dataplane_id}/dp-resource"
        params = {
            'capability_instance_id': capability_id
        }

        # Scale endpoint path
        scale_path = f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/apps/{app_id}/scale"
        scale_params = f"count={replica_count}&namespace={namespace}"

        payload = {
            "path": f"{scale_path}?{scale_params}",
            "dataPlaneId": dataplane_id,
            "capabilityInstanceId": capability_id,
            "method": "PUT"
        }

        action = "Starting" if replica_count > 0 else "Stopping"
        print(f"[*] {action} BWCE application...")
        print(f"    App ID: {app_id}")
        print(f"    Replica Count: {replica_count}")
        print(f"[DEBUG] Scale URL: {url}")
        print(f"[DEBUG] Scale payload: {json.dumps(payload, indent=2)}")

        resp = self.session.put(url, json=payload, params=params, verify=False)

        print(f"[DEBUG] Scale response status: {resp.status_code}")

        if resp.status_code in [200, 202]:
            try:
                result = resp.json()
                print(f"[DEBUG] Scale response: {json.dumps(result, indent=2)}")
                print(f"[+] Application {'started' if replica_count > 0 else 'stopped'} successfully!")
                return {"success": True, "message": result.get('message', 'Success')}
            except:
                print(f"[+] Scale request accepted")
                return {"success": True, "message": "Scale request accepted"}
        else:
            print(f"[!] Scale failed. Status: {resp.status_code}, Response: {resp.text}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}


    def start_bwce_app(self, dataplane_id, capability_id, app_id, namespace, replica_count=1):
        """
        Start a BWCE application

        Args:
            dataplane_id: The dataplane ID
            capability_id: The BWCE capability instance ID
            app_id: The application ID to start
            namespace: Kubernetes namespace
            replica_count: Number of replicas (default: 1)

        Returns:
            dict: {"success": bool, "message": str}
        """
        print(f"[*] Starting BWCE application: {app_id}")
        return self.scale_bwce_app(dataplane_id, capability_id, app_id, namespace, replica_count)


    def stop_bwce_app(self, dataplane_id, capability_id, app_id, namespace):
        """
        Stop a BWCE application

        Args:
            dataplane_id: The dataplane ID
            capability_id: The BWCE capability instance ID
            app_id: The application ID to stop
            namespace: Kubernetes namespace

        Returns:
            dict: {"success": bool, "message": str}
        """
        print(f"[*] Stopping BWCE application: {app_id}")
        return self.scale_bwce_app(dataplane_id, capability_id, app_id, namespace, 0)


    def scale_flogo_app(self, dataplane_id, capability_id, app_id, namespace, replica_count):
        """
        Scale a Flogo application (start/stop by setting replica count)

        Args:
            dataplane_id: The dataplane ID
            capability_id: The Flogo capability instance ID
            app_id: The application ID to scale
            namespace: Kubernetes namespace
            replica_count: Number of replicas (0 = stop, 1+ = start/scale)

        Returns:
            dict: {"success": bool, "message": str}
        """
        # Similar to BWCE but using flogoprovisioner endpoint
        url = f"{self.tenant_host}/tp-cp-ws/v1/data-planes/{dataplane_id}/dp-resource"
        params = {
            'capability_instance_id': capability_id
        }

        # Scale endpoint path for Flogo
        scale_path = f"/tibco/agent/integration/{capability_id}/flogoprovisioner/v1/dp/flogo/apps/{app_id}/scale"
        scale_params = f"count={replica_count}&namespace={namespace}"

        payload = {
            "dataPlaneId": dataplane_id,
            "path": f"{scale_path}?{scale_params}",
            "queryParams": {
                "capability_instance_id": capability_id
            },
            "method": "PUT"
        }

        action = "Starting" if replica_count > 0 else "Stopping"
        print(f"[*] {action} Flogo application...")
        print(f"    App ID: {app_id}")
        print(f"    Replica Count: {replica_count}")
        print(f"[DEBUG] Scale URL: {url}")
        print(f"[DEBUG] Scale payload: {json.dumps(payload, indent=2)}")

        resp = self.session.put(url, json=payload, params=params, verify=False)

        print(f"[DEBUG] Scale response status: {resp.status_code}")

        if resp.status_code in [200, 202]:
            try:
                result = resp.json()
                print(f"[DEBUG] Scale response: {json.dumps(result, indent=2)}")
                print(f"[+] Application {'started' if replica_count > 0 else 'stopped'} successfully!")
                return {"success": True, "message": result.get('message', 'Success')}
            except:
                print(f"[+] Scale request accepted")
                return {"success": True, "message": "Scale request accepted"}
        else:
            print(f"[!] Scale failed. Status: {resp.status_code}, Response: {resp.text}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}


    def start_flogo_app(self, dataplane_id, capability_id, app_id, namespace, replica_count=1):
        """
        Start a Flogo application

        Args:
            dataplane_id: The dataplane ID
            capability_id: The Flogo capability instance ID
            app_id: The application ID to start
            namespace: Kubernetes namespace
            replica_count: Number of replicas (default: 1)

        Returns:
            dict: {"success": bool, "message": str}
        """
        print(f"[*] Starting Flogo application: {app_id}")
        return self.scale_flogo_app(dataplane_id, capability_id, app_id, namespace, replica_count)


    def stop_flogo_app(self, dataplane_id, capability_id, app_id, namespace):
        """
        Stop a Flogo application

        Args:
            dataplane_id: The dataplane ID
            capability_id: The Flogo capability instance ID
            app_id: The application ID to stop
            namespace: Kubernetes namespace

        Returns:
            dict: {"success": bool, "message": str}
        """
        print(f"[*] Stopping Flogo application: {app_id}")
        return self.scale_flogo_app(dataplane_id, capability_id, app_id, namespace, 0)


    def scale_bwce_app(self, dataplane_id, capability_id, app_id, namespace, replica_count):
        """
        Scale a BWCE application to specified replica count.
        Based on start-apps-har analysis.

        Args:
            dataplane_id: The dataplane ID
            capability_id: The BWCE capability instance ID
            app_id: The application ID to scale
            namespace: Kubernetes namespace
            replica_count: Number of replicas to scale to (0 = stop, 1+ = start/scale)

        Returns:
            dict: {"success": bool, "message": str}
        """
        import time

        # Matches HAR: PUT /cp/v1/data-planes/{dp_id}/dp-resource?capability_instance_id={cap_id}
        url = f"{self.tenant_host}/cp/v1/data-planes/{dataplane_id}/dp-resource"

        params = {
            'capability_instance_id': capability_id
        }

        # Path matches HAR: /tibco/agent/integration/{cap_id}/bwprovisioner/private/v1/dp/bw/apps/{app_id}/scale?count={count}&namespace={ns}
        payload = {
            "path": f"/tibco/agent/integration/{capability_id}/bwprovisioner/private/v1/dp/bw/apps/{app_id}/scale?count={replica_count}&namespace={namespace}",
            "dataPlaneId": dataplane_id,
            "capabilityInstanceId": capability_id,
            "method": "PUT"
        }

        print(f"[DEBUG] BWCE Scale URL: {url}")
        print(f"[DEBUG] BWCE Scale params: {params}")
        print(f"[DEBUG] BWCE Scale payload: {json.dumps(payload, indent=2)}")

        resp = self.session.put(url, json=payload, params=params, verify=False)

        print(f"[DEBUG] BWCE Scale status: {resp.status_code}")

        if resp.status_code in [200, 201, 202]:
            try:
                result = resp.json()
                print(f"[DEBUG] BWCE Scale response: {json.dumps(result, indent=2)}")

                action = "started" if replica_count > 0 else "stopped"
                print(f"[+] BWCE application {action} successfully!")
                return {"success": True, "message": result.get('message', f'App {action}')}
            except:
                action = "start" if replica_count > 0 else "stop"
                print(f"[+] BWCE application {action} request accepted")
                return {"success": True, "message": f"Request accepted"}
        else:
            print(f"[!] Scale failed. Status: {resp.status_code}, Response: {resp.text}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}


    def start_bwce_app(self, dataplane_id, capability_id, app_id, namespace, replica_count=1):
        """
        Start a BWCE application

        Args:
            dataplane_id: The dataplane ID
            capability_id: The BWCE capability instance ID
            app_id: The application ID to start
            namespace: Kubernetes namespace
            replica_count: Number of replicas (default: 1)

        Returns:
            dict: {"success": bool, "message": str}
        """
        print(f"[*] Starting BWCE application: {app_id}")
        return self.scale_bwce_app(dataplane_id, capability_id, app_id, namespace, replica_count)


    def stop_bwce_app(self, dataplane_id, capability_id, app_id, namespace):
        """
        Stop a BWCE application

        Args:
            dataplane_id: The dataplane ID
            capability_id: The BWCE capability instance ID
            app_id: The application ID to stop
            namespace: Kubernetes namespace

        Returns:
            dict: {"success": bool, "message": str}
        """
        print(f"[*] Stopping BWCE application: {app_id}")
        return self.scale_bwce_app(dataplane_id, capability_id, app_id, namespace, 0)




