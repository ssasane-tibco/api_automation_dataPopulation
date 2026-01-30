"""
Start/Scale deployed BWCE and Flogo applications.

This script reads the deployed_apps.json file created during deployment
and starts (scales up) the applications.

Usage:
    python start_apps.py [--replicas N] [--bwce-only] [--flogo-only]

Options:
    --replicas N      Number of replicas to scale to (default: 1)
    --bwce-only       Only start BWCE applications
    --flogo-only      Only start Flogo applications
"""

import json
import sys
import os
import argparse

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth import SAMLAuthenticator
from services import TenantService


def main():
    parser = argparse.ArgumentParser(description='Start deployed applications')
    parser.add_argument('--replicas', type=int, default=1, help='Number of replicas to scale to')
    parser.add_argument('--bwce-only', action='store_true', help='Only start BWCE applications')
    parser.add_argument('--flogo-only', action='store_true', help='Only start Flogo applications')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    parser.add_argument('--apps-file', default='deployed_apps.json', help='Path to deployed apps file')

    args = parser.parse_args()

    print("="*60)
    print("START DEPLOYED APPLICATIONS")
    print("="*60)

    # Load deployed apps file
    if not os.path.exists(args.apps_file):
        print(f"\n[!] Error: Deployed apps file not found: {args.apps_file}")
        print("[*] Please run deploy_apps_only.py or main.py first to deploy applications")
        return 1

    try:
        with open(args.apps_file, 'r') as f:
            deployed_apps = json.load(f)
    except Exception as e:
        print(f"[!] Error reading deployed apps file: {e}")
        return 1

    # Load config
    try:
        with open(args.config, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"[!] Error reading config file: {e}")
        return 1

    tenant_host = deployed_apps.get('tenant_host')
    if not tenant_host:
        print(f"[!] Error: No tenant_host found in {args.apps_file}")
        return 1

    print(f"\n[*] Tenant Host: {tenant_host}")
    print(f"[*] Scaling to: {args.replicas} replica(s)")

    bwce_apps = deployed_apps.get('bwce_apps', [])
    flogo_apps = deployed_apps.get('flogo_apps', [])

    if args.flogo_only:
        bwce_apps = []
    if args.bwce_only:
        flogo_apps = []

    if not bwce_apps and not flogo_apps:
        print("\n[!] No applications to start")
        return 0

    print(f"[*] BWCE apps to start: {len(bwce_apps)}")
    print(f"[*] Flogo apps to start: {len(flogo_apps)}")

    # Get credentials
    credentials = config.get('credentials', {})
    invite_user_email = config.get('invite_user_email')
    invite_user_password = credentials.get('invite_user_password')

    if not invite_user_email or not invite_user_password:
        print("\n[!] Error: Missing user credentials in config.json")
        return 1

    print(f"[*] Logging in as: {invite_user_email}")

    # Login
    print("\n" + "="*60)
    print("[STEP 1] Login to Tenant")
    print("="*60)

    try:
        auth = SAMLAuthenticator(tenant_host, invite_user_email, invite_user_password)

        max_retries = 3
        for attempt in range(max_retries):
            print(f"[*] Login attempt {attempt + 1}/{max_retries}...")
            if auth.login_with_saml_flow():
                print(f"[+] Tenant Login Successful.")
                break
            else:
                if attempt < max_retries - 1:
                    print(f"[!] Login failed, retrying...")
                else:
                    print(f"[!] Login failed after {max_retries} attempts. Exiting.")
                    return 1

        tenant_service = TenantService(auth)

    except Exception as e:
        print(f"[!] Login error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Start applications
    results = {
        "bwce_apps": [],
        "flogo_apps": []
    }

    # Start BWCE applications
    if bwce_apps:
        print("\n" + "="*60)
        print("[STEP 2] Start BWCE Applications")
        print("="*60)

        for app in bwce_apps:
            app_name = app.get('app_name')
            app_id = app.get('app_id')
            dataplane_name = app.get('dataplane_name')
            dataplane_id = app.get('dataplane_id')
            capability_id = app.get('capability_id')

            print(f"\n[*] Starting: {app_name} on {dataplane_name}")
            print(f"    App ID: {app_id}")
            print(f"    Dataplane ID: {dataplane_id}")
            print(f"    Capability ID: {capability_id}")

            if not all([app_id, dataplane_id, capability_id]):
                print(f"[!] Missing required information for {app_name}")
                results["bwce_apps"].append({
                    "app_name": app_name,
                    "dataplane": dataplane_name,
                    "success": False,
                    "error": "Missing required information"
                })
                continue

            try:
                result = tenant_service.start_bwce_application(
                    dataplane_id,
                    capability_id,
                    app_id,
                    namespace='mydp-ns',
                    replicas=args.replicas
                )

                results["bwce_apps"].append({
                    "app_name": app_name,
                    "dataplane": dataplane_name,
                    "success": result.get('success'),
                    "error": result.get('error')
                })

            except Exception as e:
                print(f"[!] Error starting {app_name}: {e}")
                results["bwce_apps"].append({
                    "app_name": app_name,
                    "dataplane": dataplane_name,
                    "success": False,
                    "error": str(e)
                })

    # Start Flogo applications
    if flogo_apps:
        print("\n" + "="*60)
        print("[STEP 3] Start Flogo Applications")
        print("="*60)

        for app in flogo_apps:
            app_name = app.get('app_name')
            app_id = app.get('app_id')
            dataplane_name = app.get('dataplane_name')
            dataplane_id = app.get('dataplane_id')
            capability_id = app.get('capability_id')

            print(f"\n[*] Starting: {app_name} on {dataplane_name}")
            print(f"    App ID: {app_id}")
            print(f"    Dataplane ID: {dataplane_id}")
            print(f"    Capability ID: {capability_id}")

            if not all([app_id, dataplane_id, capability_id]):
                print(f"[!] Missing required information for {app_name}")
                results["flogo_apps"].append({
                    "app_name": app_name,
                    "dataplane": dataplane_name,
                    "success": False,
                    "error": "Missing required information"
                })
                continue

            try:
                result = tenant_service.start_flogo_application(
                    dataplane_id,
                    capability_id,
                    app_id,
                    namespace='mydp-ns',
                    replicas=args.replicas
                )

                results["flogo_apps"].append({
                    "app_name": app_name,
                    "dataplane": dataplane_name,
                    "success": result.get('success'),
                    "error": result.get('error')
                })

            except Exception as e:
                print(f"[!] Error starting {app_name}: {e}")
                results["flogo_apps"].append({
                    "app_name": app_name,
                    "dataplane": dataplane_name,
                    "success": False,
                    "error": str(e)
                })

    # Print summary
    print("\n" + "="*60)
    print("START SUMMARY")
    print("="*60)

    bwce_success = sum(1 for r in results["bwce_apps"] if r.get('success'))
    bwce_total = len(results["bwce_apps"])
    flogo_success = sum(1 for r in results["flogo_apps"] if r.get('success'))
    flogo_total = len(results["flogo_apps"])

    if bwce_total > 0:
        print(f"\n[*] BWCE Applications:")
        print(f"    Total: {bwce_total}")
        print(f"    Success: {bwce_success}")
        print(f"    Failed: {bwce_total - bwce_success}")

        if bwce_success > 0:
            print(f"\n    ✅ Successful:")
            for result in results["bwce_apps"]:
                if result.get('success'):
                    print(f"       • {result['app_name']} → {result['dataplane']}")

        if bwce_total - bwce_success > 0:
            print(f"\n    ❌ Failed:")
            for result in results["bwce_apps"]:
                if not result.get('success'):
                    print(f"       • {result['app_name']} → {result['dataplane']}")
                    print(f"         Error: {result.get('error', 'Unknown error')}")

    if flogo_total > 0:
        print(f"\n[*] Flogo Applications:")
        print(f"    Total: {flogo_total}")
        print(f"    Success: {flogo_success}")
        print(f"    Failed: {flogo_total - flogo_success}")

        if flogo_success > 0:
            print(f"\n    ✅ Successful:")
            for result in results["flogo_apps"]:
                if result.get('success'):
                    print(f"       • {result['app_name']} → {result['dataplane']}")

        if flogo_total - flogo_success > 0:
            print(f"\n    ❌ Failed:")
            for result in results["flogo_apps"]:
                if not result.get('success'):
                    print(f"       • {result['app_name']} → {result['dataplane']}")
                    print(f"         Error: {result.get('error', 'Unknown error')}")

    print("\n" + "="*60)

    # Determine exit code
    if bwce_total + flogo_total == bwce_success + flogo_success:
        print("✅ ALL APPLICATIONS STARTED SUCCESSFULLY!")
        return 0
    elif bwce_success + flogo_success > 0:
        print("⚠️  SOME APPLICATIONS FAILED TO START")
        return 1
    else:
        print("❌ ALL APPLICATIONS FAILED TO START")
        return 1


if __name__ == "__main__":
    sys.exit(main())

