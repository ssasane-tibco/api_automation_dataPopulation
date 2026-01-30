"""
Start/Stop/Scale Applications Script

This script allows you to start, stop, or scale BWCE and Flogo applications
that have already been deployed.

Usage:
    python start_stop_apps.py
"""

import json
import sys
import time
from auth import SAMLAuthenticator
from deploy_rest_api import RestApiDeployer


def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("[!] config.json not found!")
        sys.exit(1)


def login_to_tenant(config):
    """Login to tenant and return authenticated session"""
    credentials = config['credentials']
    tenant_subdomain = config['tenant_subdomain']

    tenant_host = f"https://{tenant_subdomain}.{credentials['tenant_domain']}"
    idp_host = f"https://{credentials['idp_domain']}"

    print(f"[*] Tenant Host: {tenant_host}")
    print(f"[*] Logging in as: {config['invite_user_email']}")

    auth = SAMLAuthenticator(idp_host, tenant_host)

    # Login attempts
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        print(f"\n[*] Login attempt {attempt}/{max_attempts}...")
        if auth.login_with_saml_flow(config['invite_user_email'], config['invite_user_password']):
            print("[+] Tenant Login Successful.\n")
            return auth.session, tenant_host

        if attempt < max_attempts:
            print(f"[!] Login failed. Retrying in 5 seconds...")
            time.sleep(5)

    print("[!] Login failed after all attempts.")
    return None, None


def get_deployed_apps_info(config):
    """
    Get information about deployed applications from config or user input

    Returns: list of dicts with app information
    """
    # Try to get from deployment results if available
    apps = []

    # Example structure - you'll need to customize this based on your needs
    print("\n" + "="*60)
    print("DEPLOYED APPLICATIONS")
    print("="*60)

    # For BWCE apps
    if config.get('bwce_apps'):
        for app in config['bwce_apps']:
            print(f"\nBWCE App: {app['app_name']}")
            print(f"  File: {app['app_file']}")
            print(f"  Target Dataplanes: {', '.join(app.get('target_dataplanes', ['all']))}")

    # For Flogo apps
    if config.get('flogo_apps'):
        for app in config['flogo_apps']:
            print(f"\nFlogo App: {app['app_name']}")
            print(f"  File: {app['app_file']}")
            print(f"  Target Dataplanes: {', '.join(app.get('target_dataplanes', ['all']))}")

    print("\n" + "="*60)

    return apps


def get_dataplane_info(session, tenant_host):
    """Get list of dataplanes and their capabilities"""
    import requests

    url = f"{tenant_host}/cp/v1/data-planes/capabilities-status"

    try:
        resp = session.get(url, verify=False)
        if resp.status_code == 200:
            data = resp.json()
            dataplanes = data.get('dataplanes', [])

            print("\n" + "="*60)
            print("AVAILABLE DATAPLANES")
            print("="*60)

            for idx, dp in enumerate(dataplanes, 1):
                print(f"\n{idx}. {dp.get('dp_name', 'Unknown')} (ID: {dp['dp_id']})")
                print(f"   Status: {dp['status']}")

                # Show capabilities
                for cap in dp.get('capabilities', []):
                    if cap['capability'] in ['BWCE', 'FLOGO']:
                        print(f"   - {cap['capability']}: {cap['status']} (ID: {cap['capability_instance_id']})")

            print("="*60)
            return dataplanes
        else:
            print(f"[!] Failed to get dataplanes: {resp.status_code}")
            return []
    except Exception as e:
        print(f"[!] Error getting dataplanes: {e}")
        return []


def interactive_mode(session, tenant_host):
    """Interactive mode to start/stop applications"""
    deployer = RestApiDeployer(session, tenant_host)

    print("\n" + "="*60)
    print("START/STOP APPLICATION TOOL")
    print("="*60)

    # Get dataplanes
    dataplanes = get_dataplane_info(session, tenant_host)

    if not dataplanes:
        print("[!] No dataplanes found or failed to fetch dataplanes")
        return

    # Select dataplane
    print("\nSelect dataplane (enter number):")
    try:
        dp_choice = int(input("Dataplane #: ")) - 1
        if dp_choice < 0 or dp_choice >= len(dataplanes):
            print("[!] Invalid choice")
            return

        selected_dp = dataplanes[dp_choice]
        dataplane_id = selected_dp['dp_id']

        print(f"\n[+] Selected: {selected_dp.get('dp_name', 'Unknown')} ({dataplane_id})")

    except (ValueError, IndexError):
        print("[!] Invalid input")
        return

    # Select capability type
    print("\nSelect application type:")
    print("1. BWCE")
    print("2. Flogo")

    try:
        app_type_choice = int(input("Choice: "))

        if app_type_choice == 1:
            app_type = 'BWCE'
            # Find BWCE capability
            cap_id = None
            for cap in selected_dp.get('capabilities', []):
                if cap['capability'] == 'BWCE':
                    cap_id = cap['capability_instance_id']
                    break

            if not cap_id:
                print("[!] BWCE capability not found on this dataplane")
                return

        elif app_type_choice == 2:
            app_type = 'FLOGO'
            # Find Flogo capability
            cap_id = None
            for cap in selected_dp.get('capabilities', []):
                if cap['capability'] == 'FLOGO':
                    cap_id = cap['capability_instance_id']
                    break

            if not cap_id:
                print("[!] Flogo capability not found on this dataplane")
                return
        else:
            print("[!] Invalid choice")
            return

        print(f"[+] Using {app_type} capability: {cap_id}")

    except (ValueError, IndexError):
        print("[!] Invalid input")
        return

    # Get app ID
    print("\nEnter application ID:")
    app_id = input("App ID: ").strip()

    if not app_id:
        print("[!] App ID is required")
        return

    # Get namespace
    print("\nEnter namespace (default: mydp-ns):")
    namespace = input("Namespace: ").strip() or "mydp-ns"

    # Select action
    print("\nSelect action:")
    print("1. Start (1 replica)")
    print("2. Stop (0 replicas)")
    print("3. Scale (custom replica count)")

    try:
        action_choice = int(input("Choice: "))

        if action_choice == 1:
            # Start
            if app_type == 'BWCE':
                result = deployer.start_bwce_app(dataplane_id, cap_id, app_id, namespace)
            else:
                result = deployer.start_flogo_app(dataplane_id, cap_id, app_id, namespace)

        elif action_choice == 2:
            # Stop
            if app_type == 'BWCE':
                result = deployer.stop_bwce_app(dataplane_id, cap_id, app_id, namespace)
            else:
                result = deployer.stop_flogo_app(dataplane_id, cap_id, app_id, namespace)

        elif action_choice == 3:
            # Scale
            replica_count = int(input("Enter replica count: "))
            if app_type == 'BWCE':
                result = deployer.scale_bwce_app(dataplane_id, cap_id, app_id, namespace, replica_count)
            else:
                result = deployer.scale_flogo_app(dataplane_id, cap_id, app_id, namespace, replica_count)

        else:
            print("[!] Invalid choice")
            return

        # Show result
        print("\n" + "="*60)
        if result['success']:
            print("✅ SUCCESS")
            print(f"Message: {result.get('message', 'Operation completed')}")
        else:
            print("❌ FAILED")
            print(f"Error: {result.get('error', 'Unknown error')}")
        print("="*60)

    except (ValueError, KeyError) as e:
        print(f"[!] Invalid input: {e}")
        return


def main():
    """Main function"""
    print("="*60)
    print("START/STOP/SCALE APPLICATIONS")
    print("="*60)

    # Load config
    config = load_config()

    # Login
    print("\n[STEP 1] Login to Tenant")
    print("="*60)
    session, tenant_host = login_to_tenant(config)

    if not session:
        print("[!] Failed to login. Exiting.")
        sys.exit(1)

    # Interactive mode
    try:
        while True:
            interactive_mode(session, tenant_host)

            print("\n" + "="*60)
            choice = input("Perform another operation? (y/n): ").strip().lower()
            if choice != 'y':
                break
    except KeyboardInterrupt:
        print("\n[*] Interrupted by user")

    print("\n[*] Done!")


if __name__ == "__main__":
    main()

