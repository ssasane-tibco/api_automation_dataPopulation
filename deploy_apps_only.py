#!/usr/bin/env python3
"""
Deploy Applications Only
Standalone script to deploy BWCE and Flogo applications to existing dataplanes with green capabilities.

Prerequisites:
  - Tenant subscription exists
  - User has logged in and accepted invitation
  - Dataplanes are registered and green
  - BWCE and/or Flogo capabilities are provisioned and green
"""

import json
import sys
from auth import SAMLAuthenticator
from services import TenantService
from utils import generate_tenant_relay_state
from deploy_rest_api import RestApiDeployer

def main():
    # Load configuration
    with open('config.json', 'r') as f:
        config = json.load(f)

    tenant_host = f"https://{config['target_prefix']}.cp1-my.localhost.dataplanes.pro"
    target_prefix = config['target_prefix']
    invite_user_email = config.get('invite_user_email')
    user_password = config.get('new_user_details', {}).get('password')

    app_deployment_config = config.get('app_deployment_config', {})

    if not app_deployment_config.get('enabled', False):
        print("\n⚠️  App deployment is disabled in config.json")
        print("    Set 'app_deployment_config.enabled' to true to deploy apps")
        sys.exit(0)

    print("="*60)
    print("DEPLOY APPLICATIONS ONLY")
    print("="*60)
    print("\nPrerequisites:")
    print("  * Tenant subscription exists")
    print("  * User logged in and accepted invitation")
    print("  * Dataplanes registered and green")
    print("  * Capabilities provisioned and green")
    print("="*60)

    print(f"\n[*] Tenant Host: {tenant_host}")
    print(f"[*] Logging in as: {invite_user_email}")

    # Step 1: Login
    print("\n" + "="*60)
    print("[STEP 1] Login to Tenant")
    print("="*60)

    try:
        auth = SAMLAuthenticator(tenant_host, invite_user_email, user_password)

        print("[*] Login attempt 1/3...")
        login_success = auth.run_login_flow()

        if not login_success:
            print("[*] Dynamic RelayState failed. Using generated state...")
            relay_state = generate_tenant_relay_state(target_prefix)
            login_success = auth.run_login_flow(relay_state)

        if not login_success:
            print("[!] Login failed. Cannot proceed with deployment.")
            print("\n💡 Troubleshooting:")
            print("    1. Verify credentials in config.json")
            print("    2. Ensure user has accepted invitation")
            print("    3. Try running main.py to set up everything")
            sys.exit(1)

        print("[+] Tenant Login Successful.")
        tenant_service = TenantService(auth)

        # Initialize REST API deployer
        api_deployer = RestApiDeployer(auth.session, tenant_host)

    except Exception as e:
        print(f"[!] Login error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Step 2: Get Dataplanes
    print("\n" + "="*60)
    print("[STEP 2] Get Registered Dataplanes")
    print("="*60)

    try:
        # Get dataplane status
        status_result = tenant_service.check_dataplane_status(max_wait_seconds=5, poll_interval_seconds=5)

        if not status_result.get('success'):
            print("[!] Could not get dataplane status")
            sys.exit(1)

        dataplanes = status_result.get('dataplanes', [])

        if not dataplanes:
            print("[!] No dataplanes found")
            print("\n💡 Run main.py first to register dataplanes")
            sys.exit(1)

        print(f"[+] Found {len(dataplanes)} dataplane(s)")

        # Build dataplane map: name -> {id, capabilities}
        # We need to get dataplane names - try multiple approaches
        dataplane_map = {}

        # First, try to get dataplane details via API to get actual names
        # For now, we'll build a map using config and also support direct ID matching
        dp_config = config.get('dataplane_config', {})
        dp_count = dp_config.get('dpCount', 0)
        base_name = dp_config.get('name', 'Dp1')

        # Build expected names based on config
        expected_names = []
        if dp_count == 1:
            expected_names.append(base_name)
        else:
            for i in range(1, dp_count + 1):
                expected_names.append(f"{base_name}-{i}")

        # Map each registered dataplane
        for idx, dp in enumerate(dataplanes):
            dp_id = dp.get('dp_id')

            # Try to use expected name from config based on order
            # This assumes dataplanes are returned in registration order
            if idx < len(expected_names):
                dp_name = expected_names[idx]
            else:
                dp_name = f"Dataplane-{dp_id[:8]}"

            capabilities = dp.get('capabilities', [])

            # Find BWCE and Flogo capabilities
            bwce_cap = None
            flogo_cap = None

            for cap in capabilities:
                if cap.get('capability') == 'BWCE' and cap.get('status') == 'green':
                    bwce_cap = cap.get('capability_instance_id')
                elif cap.get('capability') == 'FLOGO' and cap.get('status') == 'green':
                    flogo_cap = cap.get('capability_instance_id')

            dataplane_map[dp_name] = {
                'id': dp_id,
                'name': dp_name,
                'bwce_capability_id': bwce_cap,
                'flogo_capability_id': flogo_cap,
                'status': dp.get('status')
            }

            print(f"    - {dp_name}")
            print(f"      ID: {dp_id}")
            print(f"      Status: {dp.get('status')}")
            print(f"      BWCE: {'[OK] Green' if bwce_cap else '[X] Not available'}")
            print(f"      Flogo: {'[OK] Green' if flogo_cap else '[X] Not available'}")

    except Exception as e:
        print(f"[!] Error getting dataplanes: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Step 3: Deploy BWCE Applications
    print("\n" + "="*60)
    print("[STEP 3] Deploy BWCE Applications")
    print("="*60)

    bwce_apps = app_deployment_config.get('bwce_apps', [])
    bwce_results = []

    if not bwce_apps:
        print("[*] No BWCE applications configured")
    else:
        print(f"[*] Found {len(bwce_apps)} BWCE application(s) to deploy")

        for app in bwce_apps:
            app_name = app.get('app_name')
            app_file_name = app.get('app_file_name')
            target_dataplanes = app.get('deploy_to_dataplanes', [])

            print(f"\n[*] Deploying: {app_name}")
            print(f"    File: {app_file_name}")
            print(f"    Target dataplanes: {', '.join(target_dataplanes)}")

            for dp_name in target_dataplanes:
                if dp_name not in dataplane_map:
                    print(f"    [!] Dataplane '{dp_name}' not found - skipping")
                    bwce_results.append({
                        'app': app_name,
                        'dataplane': dp_name,
                        'success': False,
                        'error': 'Dataplane not found'
                    })
                    continue

                dp = dataplane_map[dp_name]

                if not dp['bwce_capability_id']:
                    print(f"    [!] BWCE capability not green on '{dp_name}' - skipping")
                    bwce_results.append({
                        'app': app_name,
                        'dataplane': dp_name,
                        'success': False,
                        'error': 'BWCE capability not green'
                    })
                    continue

                # Step 1: Ensure BWCE buildtype is provisioned
                print(f"\n[*] Checking/provisioning BWCE buildtype for {dp_name}...")
                buildtype_result = api_deployer.provision_bwce_buildtype(
                    dp['id'],
                    dp['bwce_capability_id'],
                    version="6.12.0-HF1"  # Use latest version
                )

                if not buildtype_result.get('success'):
                    print(f"    [!] Warning: BWCE buildtype provisioning had issues: {buildtype_result.get('error')}")
                    # Continue anyway - it may already be provisioned

                # Step 2: Deploy using REST API
                app_config = {
                    'app_file_name': app_file_name,
                    'app_name': app_name,
                    'app_folder': app_deployment_config.get('app_folder', 'apps_to_deploy'),
                    'capability_instance_id': dp['bwce_capability_id']
                }

                print(f"\n[*] Deploying {app_name} to {dp_name} using REST API...")

                # Get namespace from config
                namespace = dp.get('namespace', config.get('dataplanes', [{}])[0].get('namespace', 'mydp-ns'))

                result = api_deployer.deploy_bwce_app(
                    dp['id'],
                    dp['bwce_capability_id'],
                    namespace,
                    app_config
                )

                bwce_results.append({
                    'app': app_name,
                    'dataplane': dp_name,
                    'success': result.get('success'),
                    'build_id': result.get('build_id'),
                    'app_id': result.get('app_id'),  # Capture app_id for start_apps.py
                    'error': result.get('error')
                })

    # Step 4: Deploy Flogo Applications
    print("\n" + "="*60)
    print("[STEP 4] Deploy Flogo Applications")
    print("="*60)

    flogo_apps = app_deployment_config.get('flogo_apps', [])
    flogo_results = []

    if not flogo_apps:
        print("[*] No Flogo applications configured")
    else:
        print(f"[*] Found {len(flogo_apps)} Flogo application(s) to deploy")

        # Provision Flogo buildtype and connectors for each dataplane (only once per dataplane)
        flogo_dataplanes_provisioned = set()

        for app in flogo_apps:
            target_dataplanes = app.get('deploy_to_dataplanes', [])
            for dp_name in target_dataplanes:
                if dp_name in flogo_dataplanes_provisioned:
                    continue  # Already provisioned for this dataplane

                if dp_name not in dataplane_map:
                    continue

                dp = dataplane_map[dp_name]
                if not dp['flogo_capability_id']:
                    continue

                print(f"\n[*] Provisioning Flogo buildtype and connectors for: {dp_name}")

                # Step 1: Provision Flogo buildtype (runtime templates)
                print(f"[*] Step 1: Provisioning Flogo buildtype...")
                buildtype_result = api_deployer.provision_flogo_buildtype(
                    dp['id'],
                    dp['flogo_capability_id'],
                    version="2.26.1-b357"  # Default version from config
                )

                if not buildtype_result.get('success'):
                    print(f"[!] Failed to provision Flogo buildtype for {dp_name}")
                    continue

                # Step 2: Provision Flogo connectors
                print(f"[*] Step 2: Provisioning Flogo connectors...")
                connectors = config.get('flogo', {}).get('connectors', ['General'])
                connector_result = api_deployer.provision_flogo_connectors(
                    dp['id'],
                    dp['flogo_capability_id'],
                    connectors=connectors
                )

                if not connector_result.get('success'):
                    print(f"[!] Warning: Connector provisioning had issues for {dp_name}")
                    print(f"    Error: {connector_result.get('error')}")

                flogo_dataplanes_provisioned.add(dp_name)
                print(f"[+] Flogo prerequisites provisioned for {dp_name}")

        for app in flogo_apps:
            app_name = app.get('app_name')
            app_file_name = app.get('app_file_name')
            target_dataplanes = app.get('deploy_to_dataplanes', [])

            print(f"\n[*] Deploying: {app_name}")
            print(f"    File: {app_file_name}")
            print(f"    Target dataplanes: {', '.join(target_dataplanes)}")

            for dp_name in target_dataplanes:
                if dp_name not in dataplane_map:
                    print(f"    [!] Dataplane '{dp_name}' not found - skipping")
                    flogo_results.append({
                        'app': app_name,
                        'dataplane': dp_name,
                        'success': False,
                        'error': 'Dataplane not found'
                    })
                    continue

                dp = dataplane_map[dp_name]

                if not dp['flogo_capability_id']:
                    print(f"    [!] Flogo capability not green on '{dp_name}' - skipping")
                    flogo_results.append({
                        'app': app_name,
                        'dataplane': dp_name,
                        'success': False,
                        'error': 'Flogo capability not green'
                    })
                    continue

                # Deploy using REST API
                app_config = {
                    'app_file_name': app_file_name,
                    'app_name': app_name,
                    'app_folder': app_deployment_config.get('app_folder', 'apps_to_deploy'),
                    'capability_instance_id': dp['flogo_capability_id']
                }

                # Get namespace from config
                namespace = dp.get('namespace', config.get('dataplanes', [{}])[0].get('namespace', 'mydp-ns'))

                result = api_deployer.deploy_flogo_app(
                    dp['id'],
                    dp['flogo_capability_id'],
                    namespace,
                    app_config
                )

                flogo_results.append({
                    'app': app_name,
                    'dataplane': dp_name,
                    'success': result.get('success'),
                    'build_id': result.get('build_id'),
                    'app_id': result.get('app_id'),  # Capture app_id for start_apps.py
                    'error': result.get('error')
                })

    # Step 5: Summary
    print("\n" + "="*60)
    print("DEPLOYMENT SUMMARY")
    print("="*60)

    # BWCE Summary
    if bwce_results:
        bwce_success = sum(1 for r in bwce_results if r['success'])
        bwce_failed = len(bwce_results) - bwce_success

        print(f"\n[*] BWCE Applications:")
        print(f"    Total: {len(bwce_results)}")
        print(f"    Success: {bwce_success}")
        print(f"    Failed: {bwce_failed}")

        if bwce_success > 0:
            print(f"\n    ✅ Successful:")
            for r in bwce_results:
                if r['success']:
                    print(f"       • {r['app']} → {r['dataplane']}")
                    if r.get('build_id'):
                        print(f"         Build ID: {r['build_id']}")
                    if r.get('app_id'):
                        print(f"         App ID: {r['app_id']}")

        if bwce_failed > 0:
            print(f"\n    ❌ Failed:")
            for r in bwce_results:
                if not r['success']:
                    print(f"       • {r['app']} → {r['dataplane']}")
                    print(f"         Error: {r.get('error', 'Unknown')}")

    # Flogo Summary
    if flogo_results:
        flogo_success = sum(1 for r in flogo_results if r['success'])
        flogo_failed = len(flogo_results) - flogo_success

        print(f"\n[*] Flogo Applications:")
        print(f"    Total: {len(flogo_results)}")
        print(f"    Success: {flogo_success}")
        print(f"    Failed: {flogo_failed}")

        if flogo_success > 0:
            print(f"\n    ✅ Successful:")
            for r in flogo_results:
                if r['success']:
                    print(f"       • {r['app']} → {r['dataplane']}")
                    if r.get('build_id'):
                        print(f"         Build ID: {r['build_id']}")
                    if r.get('app_id'):
                        print(f"         App ID: {r['app_id']}")

        if flogo_failed > 0:
            print(f"\n    ❌ Failed:")
            for r in flogo_results:
                if not r['success']:
                    print(f"       • {r['app']} → {r['dataplane']}")
                    print(f"         Error: {r.get('error', 'Unknown')}")

    print("\n" + "="*60)

    # Save deployed app information to file for start_apps.py
    try:
        deployed_apps_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tenant_host": tenant_host,
            "bwce_apps": [],
            "flogo_apps": []
        }

        # Save BWCE app info with IDs
        for result in bwce_results:
            if result.get('success') and result.get('app_id'):
                dp = dataplane_map.get(result['dataplane'], {})
                deployed_apps_data["bwce_apps"].append({
                    "app_name": result['app'],
                    "app_id": result['app_id'],
                    "dataplane_name": result['dataplane'],
                    "dataplane_id": dp.get('id'),
                    "capability_id": dp.get('bwce_capability_id'),
                    "build_id": result.get('build_id')
                })

        # Save Flogo app info with IDs
        for result in flogo_results:
            if result.get('success') and result.get('app_id'):
                dp = dataplane_map.get(result['dataplane'], {})
                deployed_apps_data["flogo_apps"].append({
                    "app_name": result['app'],
                    "app_id": result['app_id'],
                    "dataplane_name": result['dataplane'],
                    "dataplane_id": dp.get('id'),
                    "capability_id": dp.get('flogo_capability_id'),
                    "build_id": result.get('build_id')
                })

        # Save to file
        if deployed_apps_data["bwce_apps"] or deployed_apps_data["flogo_apps"]:
            with open('deployed_apps.json', 'w') as f:
                json.dump(deployed_apps_data, f, indent=2)
            print(f"\n[+] Deployed app information saved to: deployed_apps.json")
            print(f"    Use 'python start_apps.py' to start the applications")

    except Exception as e:
        print(f"\n[!] Warning: Could not save deployed app information: {e}")

    # Exit code
    total_success = sum(1 for r in bwce_results + flogo_results if r['success'])
    total_apps = len(bwce_results) + len(flogo_results)

    if total_apps == 0:
        print("⚠️  No applications were deployed")
        print("\n💡 Check:")
        print("    1. app_deployment_config.bwce_apps in config.json")
        print("    2. app_deployment_config.flogo_apps in config.json")
        print("    3. Application files exist in apps_to_deploy folder")
        sys.exit(0)
    elif total_success == total_apps:
        print("✅ ALL APPLICATIONS DEPLOYED SUCCESSFULLY!")
        sys.exit(0)
    elif total_success > 0:
        print("⚠️  SOME APPLICATIONS FAILED")
        sys.exit(1)
    else:
        print("❌ ALL APPLICATIONS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()

