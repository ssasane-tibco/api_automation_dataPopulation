from auth import SAMLAuthenticator
from services import TenantService
from utils import generate_admin_relay_state, generate_tenant_relay_state, load_config, execute_commands_sequentially, save_commands_to_file
import subprocess
import sys
import argparse
import time
import json


def main():
    # Load configuration
    config = load_config()
    creds = config.get('credentials', {})
    admin_host = config.get('admin_host')
    idp_host = config.get('idp_host')
    target_prefixes = config.get('target_prefixes', [config.get('target_prefix', 'DefaultPrefix')])
    invite_email = config.get('invite_user_email')

    # Safe access to user query params with defaults
    user_params = config.get('user_query_params', {
        'order-by': '',
        'page': '1',
        'limit': '20',
        'person': ''
    })

    for target_prefix in target_prefixes:
        # Track status for summary (reset for each prefix)
        summary = {
            "Admin Login": "Pending",
            "Provision Subscription": "Pending",
            "Admin Logout": "Pending",
            "CP Login": "Pending",
            "Invite New User": "Pending",
            "CP Logout": "Pending",
            "Accept & Register User": "Pending",
            "Listing Users from CP": "Pending",
            "New User Login Verification": "Pending",
            "Register Dataplanes": "Pending",
            "Add Activation Server": "Pending",
            "Check Dataplane Status": "Pending",
            "Provision BWCE Capability": "Pending",
            "Provision Flogo Capability": "Pending",
            "Check Capability Status": "Pending",
            "Deploy BWCE Applications": "Pending",
            "Deploy Flogo Applications": "Pending"
        }

        print(f"[*] Initializing populateData for Admin Host: {admin_host} and Target Prefix: {target_prefix}")

        # 1. Admin Login
        print("\n" + "="*60)
        print("[STEP 1] Admin Login")
        print("="*60)

        admin_auth = SAMLAuthenticator(admin_host, creds.get('username'), creds.get('password'))
        login_success = admin_auth.run_login_flow()

        if not login_success:
            print("[!] No RelayState found. Skipping flow.")
            print("[*] Generating dynamic admin RelayState...")
            admin_relay_state = generate_admin_relay_state(admin_host)
            login_success = admin_auth.run_login_flow(admin_relay_state)

        if login_success:
            summary["Admin Login"] = "Pass"
            print("[+] Admin Login Successful.")
        else:
            summary["Admin Login"] = "Fail"
            print("[!] Admin Login Failed")
            print_summary(summary)
            continue

        # 2. Provision Subscription (ALWAYS RUN)
        print("\n" + "="*60)
        print("[STEP 2] Provision Subscription")
        print("="*60)

        admin_service = TenantService(admin_auth)
        provision_result = admin_service.provision_subscription(target_prefix, idp_host)

        if provision_result:
            summary["Provision Subscription"] = "Pass"
            print(f"[+] Subscription provisioning completed for: {target_prefix}")
        else:
            summary["Provision Subscription"] = "Pass (Existing)"
            print(f"[*] Subscription {target_prefix} already exists or provisioning handled")

        # --- Admin Logout ---
        if admin_auth.logout():
            summary["Admin Logout"] = "Pass"
        else:
            summary["Admin Logout"] = "Fail"

        # 3. CP Login
        tenant_host = f"https://{target_prefix.lower()}.cp1-my.localhost.dataplanes.pro"
        print(f"\n[*] Authenticating to Tenant Host: {tenant_host}")

        tenant_auth = SAMLAuthenticator(tenant_host, creds.get('username'), creds.get('password'))
        tenant_login = tenant_auth.run_login_flow()

        if not tenant_login:
            print("[*] Dynamic RelayState failed for tenant. Using generated state...")
            tenant_login = tenant_auth.run_login_flow(generate_tenant_relay_state(target_prefix))

        if tenant_login:
            summary["CP Login"] = "Pass"
            print("[+] Tenant Login Successful.")
            tenant_service = TenantService(tenant_auth)

            # Check if user already exists before inviting
            print(f"[*] Checking if {invite_email} already exists...")
            users_check = tenant_service.get_user_details(user_params)
            already_exists = False
            if users_check and users_check.get('users'):
                already_exists = any(u.get('email') == invite_email for u in users_check['users'])

            if already_exists:
                print(f"[*] User {invite_email} is already registered. Skipping invite/register.")
                summary["Invite New User"] = "Pass (Existing)"
                summary["CP Logout"] = "Skipped"
                summary["Accept & Register User"] = "Pass (Existing)"

                # Use the current tenant session (CP admin session) to continue workflow
                print(f"\n[*] Using existing authenticated session for workflow continuation...")
                try:
                    # Since we're already authenticated as CP admin and user exists,
                    # we can use the tenant_service which already has admin privileges
                    summary["New User Login Verification"] = "Pass (Existing)"
                    summary["Listing Users from CP"] = "Pass (Existing)"

                    # Use tenant_service (CP admin session) for subsequent operations
                    new_user_service = tenant_service
                    new_user_auth = tenant_auth
                    print(f"[+] Using CP admin session for workflow continuation (user {invite_email} already exists)")
                except Exception as e:
                    print(f"[!] Error setting up session: {e}")
                    summary["New User Login Verification"] = "Fail"
                    summary["Listing Users from CP"] = "Skipped"
            else:
                # 4. Invite New User
                if invite_email:
                    if tenant_service.invite_new_user(invite_email):
                        summary["Invite New User"] = "Pass"

                        # --- CP Logout (after invitation) ---
                        print("\n" + "="*60)
                        print("[STEP 4.5] CP Logout")
                        print("="*60)
                        print("[*] Logging out from CP after sending invitation...")
                        if tenant_auth.logout():
                            summary["CP Logout"] = "Pass"
                            print("[+] CP logout successful")
                        else:
                            summary["CP Logout"] = "Fail"
                            print("[!] CP logout failed")

                        # --- 4.1 Accept Invite & Register ---
                        print(f"\n[*] STEP 4.1: Starting Accept/Register flow for {invite_email}...")
                        try:
                            # Use absolute path for cross-platform compatibility (works in CMD and Git Bash)
                            import os
                            script_dir = os.path.dirname(os.path.abspath(__file__))
                            accept_invite_path = os.path.join(script_dir, "accept_invite.py")

                            result = subprocess.run([sys.executable, accept_invite_path, invite_email],
                                                  capture_output=True, text=True, cwd=script_dir)

                            if result.stdout:
                                print("\n" + "-"*20 + " SUBPROCESS OUTPUT " + "-"*20)
                                print(result.stdout.strip())
                                print("-" * 59 + "\n")

                            if result.returncode == 0:
                                print(f"[+] STEP 4.1 COMPLETE: Registration flow finished for {invite_email}.")
                                summary["Accept & Register User"] = "Pass"

                                # Wait for user account to be fully activated
                                import time
                                print(f"[*] Waiting 20 seconds for user account activation...")
                                time.sleep(20)

                                # 5. New User Login Verification (Execute first to establish new user session)
                                print("\n" + "="*60)
                                print("[STEP 5] New User Login Verification")
                                print("="*60)

                                print(f"[*] Verifying login for newly invited user: {invite_email}...")
                                print(f"[*] Waiting 30 seconds for full user activation and permission propagation...")
                                time.sleep(30)

                                try:
                                    # Create new auth instance for the invited user
                                    new_user_password = config.get('new_user_details', {}).get('password', 'Tibco@2025')
                                    new_user_auth = SAMLAuthenticator(tenant_host, invite_email, new_user_password)

                                    # Attempt login with retry
                                    max_retries = 5
                                    login_success = False

                                    for attempt in range(1, max_retries + 1):
                                        print(f"[*] Login attempt {attempt}/{max_retries} for new user {invite_email}...")

                                        new_user_login = new_user_auth.run_login_flow()
                                        if not new_user_login:
                                            print("[*] Dynamic RelayState failed for new user. Using generated state...")
                                            new_user_login = new_user_auth.run_login_flow(generate_tenant_relay_state(target_prefix))

                                        if new_user_login:
                                            login_success = True
                                            print(f"[+] Successfully logged in as {invite_email}")
                                            summary["New User Login Verification"] = "Pass"
                                            break
                                        else:
                                            if attempt < max_retries:
                                                wait_time = 15 * attempt  # Increasing wait time: 15, 30, 45, 60 seconds
                                                print(f"[!] Login attempt {attempt} failed. Waiting {wait_time} seconds before retry...")
                                                time.sleep(wait_time)

                                    if not login_success:
                                        print(f"[!] Failed to login with new user {invite_email} after {max_retries} attempts")
                                        print(f"[!] Error: ATMOSPHERE-11004 typically means user permissions are not fully propagated")
                                        print(f"[*] The user IS registered and active, but may need more time for permissions")
                                        print(f"[*] You can manually verify login at: {tenant_host}")
                                        summary["New User Login Verification"] = "Fail (Permissions Pending)"
                                        summary["Listing Users from CP"] = "Skipped"
                                    else:
                                        # 6. Listing Users from CP (Execute after successful new user login)
                                        print("\n" + "="*60)
                                        print("[STEP 6] Listing Users from CP")
                                        print("="*60)

                                        # Now create TenantService with the NEW USER's authenticated session
                                        new_user_service = TenantService(new_user_auth)

                                        print("[*] Verifying final user list with new user session...")
                                        users_data = new_user_service.get_user_details(user_params)
                                        if users_data and users_data.get('users'):
                                            summary["Listing Users from CP"] = "Pass"
                                            print(f"\n[+] Successfully retrieved {len(users_data['users'])} users:")
                                            for idx, user in enumerate(users_data['users']):
                                                print(f"    {idx+1}. {user.get('email')} ({user.get('firstName')} {user.get('lastName')})")

                                            # Show user details for invited user
                                            print(f"\n[*] Verifying invited user {invite_email} details...")
                                            user_info = new_user_service.get_specific_user(invite_email)
                                            if user_info:
                                                print(f"[+] User activated: {user_info.get('email')}")
                                                print(f"    Name: {user_info.get('firstName')} {user_info.get('lastName')}")
                                                print(f"    Roles: {', '.join([r.get('roleId', 'N/A') for r in user_info.get('roles', [])])}")
                                                print(f"[+] User {invite_email} is fully registered and can access CP!")
                                        else:
                                            summary["Listing Users from CP"] = "Fail"
                                            print("[!] Failed to retrieve users from CP with new user session")

                                except Exception as e:
                                    print(f"[!] New User Login Verification Error: {e}")
                                    summary["New User Login Verification"] = "Fail"
                                    summary["Listing Users from CP"] = "Skipped"
                            else:
                                print(f"[!] STEP 4.1 FAILED: registration script exited with code {result.returncode}")
                                if result.stderr:
                                    print(f"[!] Error Details:\n{result.stderr.strip()}")
                                summary["Accept & Register User"] = "Fail (Script Error)"
                        except Exception as e:
                            print(f"[!] Exception during registration subprocess: {e}")
                            summary["Accept & Register User"] = "Error"
                    else:
                        summary["Invite New User"] = "Fail"
                        summary["Accept & Register User"] = "Skipped"
                        summary["Listing Users from CP"] = "Skipped"
                else:
                    summary["Invite New User"] = "Skipped"
                    summary["Accept & Register User"] = "Skipped"
                    summary["Listing Users from CP"] = "Skipped"

                # Step 7: Register Dataplanes (if user login was successful)
                if "Pass" in summary["New User Login Verification"]:
                    print("\n" + "="*60)
                    print("[STEP 7] Register Dataplanes")
                    print("="*60)

                    try:
                        dataplane_config = config.get('dataplane_config', {})
                        dp_count = dataplane_config.get('dpCount', 0)

                        if dp_count > 0:
                            print(f"[*] Registering {dp_count} dataplane(s)...")

                            # Use the new user's authenticated session for dataplane registration
                            # (they have the necessary permissions)
                            all_results = []
                            all_commands = []

                            # Get status check configuration
                            status_check_config = config.get('dataplane_status_check', {})
                            status_check_enabled = status_check_config.get('enabled', False)
                            max_wait = status_check_config.get('max_wait_seconds', 120)
                            poll_interval = status_check_config.get('poll_interval_seconds', 10)

                            for i in range(1, dp_count + 1):
                                print(f"\n[*] Registering Dataplane {i}/{dp_count}")

                                # Create unique config for this dataplane
                                dp_config = dataplane_config.copy()

                                # Generate unique names with suffix
                                if dp_count > 1:
                                    base_name = dataplane_config.get('name', 'Dp1')
                                    base_namespace = dataplane_config.get('namespace', 'default')
                                    base_sa = dataplane_config.get('serviceAccountName', 'tibco-sa')

                                    dp_config['name'] = f"{base_name}-{i}"
                                    dp_config['namespace'] = f"{baseNamespace}-{i}"
                                    dp_config['serviceAccountName'] = f"{base_sa}-{i}"

                                print(f"    Name: {dp_config['name']}")
                                print(f"    Namespace: {dp_config['namespace']}")

                                # Register dataplane using the new user's session
                                result = new_user_service.register_dataplane(dp_config)

                                if result and result.get('success'):
                                    commands = result.get('commands', [])
                                    dataplane_id = result.get('dataplane_id', '')

                                    print(f"[+] Dataplane {i} registered successfully!")
                                    print(f"    ID: {dataplane_id}")
                                    print(f"    Commands: {len(commands)}")

                                    all_results.append({
                                        "index": i,
                                        "name": dp_config['name'],
                                        "namespace": dp_config['namespace'],
                                        "success": True,
                                        "commands": commands,
                                        "dataplane_id": dataplane_id,
                                        "status_check_result": None
                                    })

                                    all_commands.extend(commands)

                                    # Save commands to file
                                    filename = f"dataplane_{dp_config['name']}_commands.txt"
                                    save_commands_to_file(commands, filename)

                                    # Execute commands immediately after registration
                                    print(f"\n{'='*60}")
                                    print(f"[*] Executing installation commands for {dp_config['name']}")
                                    print(f"{'='*60}")
                                    execution_result = execute_commands_sequentially(commands)

                                    if not execution_result.get('success'):
                                        print(f"[!] Some commands failed. Dataplane may not come up properly.")
                                        print(f"    Executed: {execution_result.get('executed')}")
                                        print(f"    Failed: {execution_result.get('failed')}")
                                    else:
                                        print(f"[+] All {len(commands)} commands executed successfully!")

                                    # Check status immediately after registration if enabled
                                    if status_check_enabled:
                                        print(f"\n{'='*60}")
                                        print(f"[STEP 7.{i}] Check Status for Dataplane {i}/{dp_count}")
                                        print(f"{'='*60}")
                                        print(f"[*] Checking status for: {dp_config['name']} (ID: {dataplane_id})")
                                        print(f"    Max Wait Time: {max_wait} seconds")
                                        print(f"    Poll Interval: {poll_interval} seconds")

                                        try:
                                            # Check status for THIS specific dataplane
                                            status_result = new_user_service.check_dataplane_status(
                                                dataplane_id=dataplane_id,
                                                max_wait_seconds=max_wait,
                                                poll_interval_seconds=poll_interval
                                            )

                                            # Store status result with this dataplane
                                            all_results[-1]['status_check_result'] = status_result

                                            if status_result and status_result.get('success') and status_result.get('all_green'):
                                                print(f"\n[+] Dataplane {i} ({dp_config['name']}) is GREEN!")
                                                print(f"    Time taken: {status_result.get('elapsed_time', 0):.1f} seconds")
                                            else:
                                                print(f"\n[!] Dataplane {i} ({dp_config['name']}) did not reach green status")
                                                if status_result:
                                                    print(f"    Time elapsed: {status_result.get('elapsed_time', 0):.1f} seconds")

                                        except Exception as e:
                                            print(f"[!] Status check error for dataplane {i}: {e}")
                                            all_results[-1]['status_check_result'] = {"success": False, "error": str(e)}

                                else:
                                    print(f"[!] Dataplane {i} registration failed")
                                    all_results.append({
                                        "index": i,
                                        "name": dp_config.get('name'),
                                        "success": False,
                                        "status_check_result": None
                                    })

                            # Summary
                            successful = [r for r in all_results if r['success']]
                            failed = [r for r in all_results if not r['success']]

                            print(f"\n{'='*60}")
                            print(f"[*] Dataplane Registration & Status Summary:")
                            print(f"{'='*60}")
                            print(f"    Total: {dp_count}")
                            print(f"    Successful Registrations: {len(successful)}")
                            print(f"    Failed Registrations: {len(failed)}")

                            # Status check summary
                            if status_check_enabled:
                                green_count = 0
                                not_green_count = 0
                                for result in successful:
                                    status_result = result.get('status_check_result')
                                    if status_result and status_result.get('success') and status_result.get('all_green'):
                                        green_count += 1
                                    else:
                                        not_green_count += 1

                                print(f"    Status Check: Enabled")
                                print(f"    Green Dataplanes: {green_count}/{len(successful)}")
                                if not_green_count > 0:
                                    print(f"    Not Green: {not_green_count}/{len(successful)}")

                            print(f"{'='*60}\n")

                            if len(successful) > 0:
                                # Commands are now executed immediately after each dataplane registration
                                # Summary is based on registration and status check results
                                summary["Register Dataplanes"] = f"Pass ({len(successful)}/{dp_count})"

                                # Update summary with status check results
                                if status_check_enabled:
                                    green_count = sum(1 for r in successful if r.get('status_check_result', {}).get('all_green'))
                                    if green_count == len(successful):
                                        summary["Check Dataplane Status"] = f"Pass ({green_count}/{len(successful)} DPs green)"
                                    elif green_count > 0:
                                        summary["Check Dataplane Status"] = f"Partial ({green_count}/{len(successful)} DPs green)"
                                    else:
                                        summary["Check Dataplane Status"] = f"Fail (0/{len(successful)} DPs green)"
                            else:
                                summary["Register Dataplanes"] = "Fail"
                                summary["Check Dataplane Status"] = "Skipped (No dataplanes registered)"
                        else:
                            summary["Register Dataplanes"] = "Skipped (dpCount=0)"
                            summary["Check Dataplane Status"] = "Skipped (dpCount=0)"
                            print("[*] dpCount is 0, skipping dataplane registration")

                    except Exception as e:
                        print(f"[!] Dataplane Registration Error: {e}")
                        import traceback
                        traceback.print_exc()
                        summary["Register Dataplanes"] = "Error"

                    # Step 8: Add Activation Server (after dataplane registration)
                    activation_server_resource_id = None
                    if summary["Register Dataplanes"] not in ["Pending", "Skipped (dpCount=0)", "Skipped (Prerequisites not met)", "Error", "Fail"]:
                        print("\n" + "="*60)
                        print("[STEP 8] Add Activation Server")
                        print("="*60)

                        try:
                            activation_server_config = config.get('activation_server_config', {})

                            if activation_server_config.get('url') and activation_server_config.get('name'):
                                print(f"[*] Adding activation server...")
                                print(f"    URL: {activation_server_config.get('url')}")
                                print(f"    Version: {activation_server_config.get('version', '1.8.0')}")

                                # Add activation server using the new user's session
                                result = new_user_service.add_activation_server(activation_server_config)

                                if result and result.get('success'):
                                    activation_server_resource_id = result.get('resource_instance_id', '')
                                    print(f"[+] Activation server added successfully!")
                                    print(f"    Resource Instance ID: {activation_server_resource_id}")
                                    summary["Add Activation Server"] = "Pass"

                                    # Step 8.5: Associate activation server with all dataplanes
                                    if activation_server_resource_id and 'all_results' in locals() and all_results:
                                        print("\n" + "="*60)
                                        print("[STEP 8.5] Associate Activation Server with Dataplanes")
                                        print("="*60)

                                        try:
                                            # Build dataplane list from registration results
                                            dataplanes = []
                                            for dp_result in all_results:
                                                if dp_result.get('success') and dp_result.get('dataplane_id'):
                                                    dataplanes.append({
                                                        'id': dp_result.get('dataplane_id'),
                                                        'name': dp_result.get('name', 'Unknown')
                                                    })

                                            if dataplanes:
                                                # Associate activation server with all dataplanes
                                                association_result = new_user_service.use_global_activation_server(
                                                    dataplanes,
                                                    activation_server_resource_id
                                                )

                                                if association_result and association_result.get('success'):
                                                    print(f"[+] Activation server associated with all dataplanes successfully!")
                                                else:
                                                    failed_count = association_result.get('failed', 0) if association_result else len(dataplanes)
                                                    print(f"[!] Some dataplane associations failed ({failed_count}/{len(dataplanes)})")
                                            else:
                                                print("[!] No dataplanes available for activation server association")

                                        except Exception as e:
                                            print(f"[!] Error associating activation server with dataplanes: {e}")
                                            import traceback
                                            traceback.print_exc()

                                else:
                                    print(f"[!] Activation server addition failed")
                                    summary["Add Activation Server"] = "Fail"
                            else:
                                summary["Add Activation Server"] = "Skipped (No config)"
                                print("[*] No activation server configuration found, skipping")

                        except Exception as e:
                            print(f"[!] Activation Server Addition Error: {e}")
                            import traceback
                            traceback.print_exc()
                            summary["Add Activation Server"] = "Error"

                        # Step 8.5: Link Activation Server to Dataplanes (after activation server addition)
                        # This ensures all dataplanes can use the centralized activation server for licensing
                        if summary["Add Activation Server"] == "Pass" and activation_server_resource_id:
                            try:
                                # Get list of registered dataplane IDs
                                if 'all_results' in locals():
                                    dataplane_ids = [dp.get('dataplane_id') for dp in all_results if dp.get('success') and dp.get('dataplane_id')]

                                    if dataplane_ids:
                                        link_result = new_user_service.use_global_activation_server_for_dataplanes(
                                            dataplane_ids,
                                            activation_server_resource_id
                                        )

                                        if link_result.get('successful') == link_result.get('total'):
                                            summary["Link Activation Server"] = f"Pass ({link_result['successful']}/{link_result['total']})"
                                        elif link_result.get('successful') > 0:
                                            summary["Link Activation Server"] = f"Partial ({link_result['successful']}/{link_result['total']})"
                                        else:
                                            summary["Link Activation Server"] = "Fail"
                                    else:
                                        print("[*] No dataplanes to link activation server to")
                                        summary["Link Activation Server"] = "Skipped (No dataplanes)"
                                else:
                                    summary["Link Activation Server"] = "Skipped (No dataplanes registered)"

                            except Exception as e:
                                print(f"[!] Activation Server Linking Error: {e}")
                                import traceback
                                traceback.print_exc()
                                summary["Link Activation Server"] = "Error"
                        else:
                            summary["Link Activation Server"] = "Skipped (No activation server)"

                    else:
                        summary["Add Activation Server"] = "Skipped (Prerequisites not met)"
                        summary["Link Activation Server"] = "Skipped (Prerequisites not met)"
                        print("[*] Skipping activation server addition (dataplane registration not successful)")

                    # Step 9: Provision BWCE Capability (after activation server)
                    bwce_config = config.get('bwce_capability_config', {})
                    if bwce_config.get('enabled', False):
                        # Only provision if dataplanes were registered and status checks passed
                        if summary["Register Dataplanes"] not in ["Pending", "Skipped (dpCount=0)", "Skipped (Prerequisites not met)", "Error", "Fail"]:
                            print("\n" + "="*60)
                            print("[STEP 9] Provision BWCE Capability")
                            print("="*60)

                            try:
                                provision_per_dataplane = bwce_config.get('provision_per_dataplane', True)
                                bwce_results = []

                                if provision_per_dataplane and 'all_results' in locals():
                                    # Provision BWCE for each dataplane that has green status
                                    for dp_result in all_results:
                                        if not dp_result.get('success'):
                                            continue

                                        # Check if dataplane is green (if status check was enabled)
                                        status_check_enabled = config.get('dataplane_status_check', {}).get('enabled', False)
                                        if status_check_enabled:
                                            status_result = dp_result.get('status_check_result', {})
                                            if not (status_result.get('success') and status_result.get('all_green')):
                                                print(f"\n[!] Skipping BWCE for {dp_result['name']} - dataplane not green")
                                                bwce_results.append({
                                                    "dataplane_name": dp_result['name'],
                                                    "success": False,
                                                    "error": "Dataplane not green"
                                                })
                                                continue

                                        dataplane_id = dp_result.get('dataplane_id')
                                        dataplane_name = dp_result.get('name')

                                        print(f"\n{'='*60}")
                                        print(f"[*] Provisioning BWCE for: {dataplane_name}")
                                        print(f"{'='*60}")

                                        # Check if resources should be created before BWCE provisioning
                                        resources_config = config.get('dataplane_resources_config', {})
                                        should_create_resources = resources_config.get('create_resources', False)

                                        if should_create_resources:
                                            print(f"\n[*] Creating dataplane resources for {dataplane_name}...")

                                            # Create Storage Resource
                                            storage_config = resources_config.get('storage', {})
                                            if storage_config:
                                                storage_name = storage_config.get('name')

                                                # ALWAYS create new resources to avoid cross-subscription conflicts
                                                # Even if a resource with the same name exists, it may be from a different subscription
                                                print(f"[*] Creating storage resource '{storage_name}' for this dataplane...")
                                                storage_result = new_user_service.create_storage_resource(dataplane_id, storage_config)

                                                if storage_result.get('success'):
                                                    # Creation succeeded - use the newly created resource ID DIRECTLY
                                                    storage_resource_id = storage_result.get('resource_instance_id')
                                                    print(f"[+] Using newly created storage resource ID: {storage_resource_id}")
                                                    bwce_config['storage_resource_id'] = storage_resource_id
                                                else:
                                                    # If creation fails, check if it already exists
                                                    existing_storage_id = new_user_service.get_storage_resource_id(dataplane_id, storage_name)

                                                    if existing_storage_id:
                                                        print(f"[+] Storage resource '{storage_name}' already exists, using it")
                                                        print(f"    Resource ID: {existing_storage_id}")
                                                        bwce_config['storage_resource_id'] = existing_storage_id
                                                    else:
                                                        print(f"[!] Failed to create storage resource")
                                                        bwce_results.append({
                                                            "dataplane_name": dataplane_name,
                                                            "success": False,
                                                            "error": f"Storage creation failed: {storage_result.get('error')}"
                                                        })
                                                        continue

                                            # Create Ingress Resource
                                            ingress_config = resources_config.get('ingress', {})
                                            if ingress_config:
                                                ingress_name = ingress_config.get('name')

                                                # ALWAYS create new resources to avoid cross-subscription conflicts
                                                print(f"[*] Creating ingress resource '{ingress_name}' for this dataplane...")
                                                ingress_result = new_user_service.create_ingress_resource(dataplane_id, ingress_config)

                                                if ingress_result.get('success'):
                                                    # Creation succeeded - use the newly created resource ID DIRECTLY
                                                    ingress_resource_id = ingress_result.get('resource_instance_id')
                                                    ingress_fqdn = ingress_result.get('fqdn', '')
                                                    print(f"[+] Using newly created ingress resource ID: {ingress_resource_id}")
                                                    if ingress_fqdn:
                                                        print(f"    FQDN: {ingress_fqdn}")
                                                    bwce_config['ingress_resource_id'] = ingress_resource_id
                                                else:
                                                    # If creation fails, check if it already exists
                                                    existing_ingress_id, existing_fqdn = new_user_service.get_ingress_resource_id(dataplane_id, ingress_name)

                                                    if existing_ingress_id:
                                                        print(f"[+] Ingress resource '{ingress_name}' already exists, using it")
                                                        print(f"    Resource ID: {existing_ingress_id}")
                                                        print(f"    FQDN: {existing_fqdn}")
                                                        bwce_config['ingress_resource_id'] = existing_ingress_id
                                                    else:
                                                        print(f"[!] Failed to create ingress resource")
                                                        bwce_results.append({
                                                            "dataplane_name": dataplane_name,
                                                            "success": False,
                                                            "error": f"Ingress creation failed: {ingress_result.get('error')}"
                                                        })
                                                        continue

                                                # Wait for resource propagation
                                                print(f"[*] Waiting 10 seconds for resource propagation...")
                                                import time
                                                time.sleep(10)

                                        # Provision BWCE
                                        provision_result = new_user_service.provision_bwce_capability(
                                            dataplane_id,
                                            dataplane_name,
                                            bwce_config
                                        )

                                        if provision_result.get('success'):
                                            capability_instance_id = provision_result.get('capability_instance_id')

                                            # CRITICAL: Provision BWCE buildtype/version (MANDATORY before app deployment)
                                            print(f"\n[*] Provisioning BWCE buildtype version (required for app deployment)...")
                                            bwce_version = bwce_config.get('buildtype_version', '6.12.0-HF1')

                                            # Wait a bit for capability to initialize
                                            print(f"[*] Waiting 5 seconds for BWCE capability to initialize...")
                                            time.sleep(5)

                                            buildtype_result = new_user_service.provision_bwce_buildtype(
                                                dataplane_id,
                                                capability_instance_id,
                                                bwce_version
                                            )

                                            if buildtype_result.get('success'):
                                                print(f"[+] BWCE buildtype {bwce_version} provisioned successfully!")
                                            else:
                                                print(f"[!] BWCE buildtype provisioning failed: {buildtype_result.get('error')}")
                                                print(f"[!] WARNING: App deployment may fail without buildtype!")

                                            # Wait for BWCE to become green if configured
                                            if bwce_config.get('wait_for_green', True):
                                                max_wait = bwce_config.get('max_wait_seconds', 300)
                                                poll_interval = bwce_config.get('poll_interval_seconds', 15)

                                                status_result = new_user_service.check_bwce_capability_status(
                                                    dataplane_id,
                                                    capability_instance_id,
                                                    max_wait,
                                                    poll_interval
                                                )

                                                bwce_results.append({
                                                    "dataplane_name": dataplane_name,
                                                    "success": status_result.get('success'),
                                                    "status": status_result.get('status'),
                                                    "capability_instance_id": capability_instance_id,
                                                    "buildtype_provisioned": buildtype_result.get('success'),
                                                    "buildtype_version": bwce_version,
                                                    "elapsed_time": status_result.get('elapsed_time', 0)
                                                })
                                            else:
                                                bwce_results.append({
                                                    "dataplane_name": dataplane_name,
                                                    "success": True,
                                                    "status": "provisioned",
                                                    "capability_instance_id": capability_instance_id,
                                                    "buildtype_provisioned": buildtype_result.get('success'),
                                                    "buildtype_version": bwce_version
                                                })
                                        else:
                                            print(f"[!] BWCE provisioning failed for {dataplane_name}")
                                            bwce_results.append({
                                                "dataplane_name": dataplane_name,
                                                "success": False,
                                                "error": provision_result.get('error', 'Unknown error')
                                            })

                                # Summary
                                print(f"\n{'='*60}")
                                print(f"[*] BWCE Provisioning Summary:")
                                print(f"{'='*60}")

                                successful_bwce = [r for r in bwce_results if r.get('success')]
                                failed_bwce = [r for r in bwce_results if not r.get('success')]

                                print(f"    Total Dataplanes: {len(bwce_results)}")
                                print(f"    Successful: {len(successful_bwce)}")
                                print(f"    Failed: {len(failed_bwce)}")

                                for result in bwce_results:
                                    status_emoji = "[+]" if result.get('success') else "[!]"
                                    dp_name = result.get('dataplane_name', 'Unknown')
                                    status = result.get('status', 'unknown')

                                    print(f"\n    {status_emoji} {dp_name}: {status.upper()}")
                                    if result.get('success') and result.get('elapsed_time'):
                                        print(f"        Time: {result.get('elapsed_time', 0):.1f}s")
                                    if result.get('capability_instance_id'):
                                        print(f"        Instance ID: {result.get('capability_instance_id')}")
                                    if not result.get('success') and result.get('error'):
                                        print(f"        Error: {result.get('error')}")

                                print(f"{'='*60}\n")

                                # Update summary
                                if len(successful_bwce) == len(bwce_results) and len(successful_bwce) > 0:
                                    summary["Provision BWCE Capability"] = f"Pass ({len(successful_bwce)}/{len(bwce_results)})"
                                elif len(successful_bwce) > 0:
                                    summary["Provision BWCE Capability"] = f"Partial ({len(successful_bwce)}/{len(bwce_results)})"
                                else:
                                    summary["Provision BWCE Capability"] = "Fail"

                            except Exception as e:
                                print(f"[!] BWCE Provisioning Error: {e}")
                                import traceback
                                traceback.print_exc()
                                summary["Provision BWCE Capability"] = "Error"
                                # Don't set bwce_results to skip Flogo - let Flogo run independently

                            # Step 9.5: Provision Flogo Capability (runs independently of BWCE)
                            flogo_config = config.get('flogo_capability_config', {})
                            if flogo_config.get('enabled', False):
                                print("\n" + "="*60)
                                print("[STEP 9.5] Provision Flogo Capability")
                                print("="*60)

                                try:
                                    provision_per_dataplane = flogo_config.get('provision_per_dataplane', True)
                                    flogo_results = []

                                    if provision_per_dataplane and 'all_results' in locals():
                                        # Provision Flogo for each dataplane that has green status
                                        for dp_result in all_results:
                                            if not dp_result.get('success'):
                                                continue

                                            # Check if dataplane is green (if status check was enabled)
                                            status_check_enabled = config.get('dataplane_status_check', {}).get('enabled', False)
                                            if status_check_enabled:
                                                status_result = dp_result.get('status_check_result', {})
                                                if not (status_result.get('success') and status_result.get('all_green')):
                                                    print(f"\n[!] Skipping Flogo for {dp_result['name']} - dataplane not green")
                                                    flogo_results.append({
                                                        "dataplane_name": dp_result['name'],
                                                        "success": False,
                                                        "error": "Dataplane not green"
                                                    })
                                                    continue

                                            dataplane_id = dp_result.get('dataplane_id')
                                            dataplane_name = dp_result.get('name')

                                            print(f"\n{'='*60}")
                                            print(f"[*] Provisioning Flogo for: {dataplane_name}")
                                            print(f"{'='*60}")

                                            # Use existing resources created during BWCE provisioning
                                            # Set resource IDs from bwce_config if available
                                            if 'bwce_config' in locals():
                                                if 'storage_resource_id' in bwce_config:
                                                    flogo_config['storage_resource_id'] = bwce_config['storage_resource_id']
                                                if 'ingress_resource_id' in bwce_config:
                                                    flogo_config['ingress_resource_id'] = bwce_config['ingress_resource_id']

                                            # Provision Flogo
                                            provision_result = new_user_service.provision_flogo_capability(
                                                dataplane_id,
                                                dataplane_name,
                                                flogo_config
                                            )

                                            if provision_result.get('success'):
                                                capability_instance_id = provision_result.get('capability_instance_id')

                                                # Wait for Flogo to become green if configured
                                                if flogo_config.get('wait_for_green', True):
                                                    max_wait = flogo_config.get('max_wait_seconds', 300)
                                                    poll_interval = flogo_config.get('poll_interval_seconds', 15)

                                                    status_result = new_user_service.check_flogo_capability_status(
                                                        dataplane_id,
                                                        capability_instance_id,
                                                        max_wait,
                                                        poll_interval
                                                    )

                                                    flogo_results.append({
                                                        "dataplane_name": dataplane_name,
                                                        "success": status_result.get('success'),
                                                        "status": status_result.get('status'),
                                                        "capability_instance_id": capability_instance_id,
                                                        "elapsed_time": status_result.get('elapsed_time', 0)
                                                    })
                                                else:
                                                    flogo_results.append({
                                                        "dataplane_name": dataplane_name,
                                                        "success": True,
                                                        "status": "provisioned",
                                                        "capability_instance_id": capability_instance_id
                                                    })
                                            else:
                                                print(f"[!] Flogo provisioning failed for {dataplane_name}")
                                                flogo_results.append({
                                                    "dataplane_name": dataplane_name,
                                                    "success": False,
                                                    "error": provision_result.get('error', 'Unknown error')
                                                })

                                    # Summary
                                    print(f"\n{'='*60}")
                                    print(f"[*] Flogo Provisioning Summary:")
                                    print(f"{'='*60}")

                                    successful_flogo = [r for r in flogo_results if r.get('success')]
                                    failed_flogo = [r for r in flogo_results if not r.get('success')]

                                    print(f"    Total Dataplanes: {len(flogo_results)}")
                                    print(f"    Successful: {len(successful_flogo)}")
                                    print(f"    Failed: {len(failed_flogo)}")

                                    for result in flogo_results:
                                        status_emoji = "[+]" if result.get('success') else "[!]"
                                        dp_name = result.get('dataplane_name', 'Unknown')
                                        status = result.get('status', 'unknown')

                                        print(f"\n    {status_emoji} {dp_name}: {status.upper()}")
                                        if result.get('success') and result.get('elapsed_time'):
                                            print(f"        Time: {result.get('elapsed_time', 0):.1f}s")
                                        if result.get('capability_instance_id'):
                                            print(f"        Instance ID: {result.get('capability_instance_id')}")
                                        if not result.get('success') and result.get('error'):
                                            print(f"        Error: {result.get('error')}")

                                    print(f"{'='*60}\n")

                                    # Update summary
                                    if len(successful_flogo) == len(flogo_results) and len(successful_flogo) > 0:
                                        summary["Provision Flogo Capability"] = f"Pass ({len(successful_flogo)}/{len(flogo_results)})"
                                    elif len(successful_flogo) > 0:
                                        summary["Provision Flogo Capability"] = f"Partial ({len(successful_flogo)}/{len(flogo_results)})"
                                    else:
                                        summary["Provision Flogo Capability"] = "Fail"

                                except Exception as e:
                                    print(f"[!] Flogo Provisioning Error: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    summary["Provision Flogo Capability"] = "Error"
                            else:
                                summary["Provision Flogo Capability"] = "Skipped (Disabled in config)"
                            print("[*] Flogo provisioning is disabled in config.json")

                        # Step 9.9: Combined Capability Status Check (for all provisioned capabilities)
                        combined_check_config = config.get('combined_capability_status_check', {})
                        if combined_check_config.get('enabled', True):
                            # Initialize status results storage
                            capability_status_results = {}

                            # Check if we have any capabilities to check
                            has_bwce_to_check = 'bwce_results' in locals() and len(bwce_results) > 0
                            has_flogo_to_check = 'flogo_results' in locals() and len(flogo_results) > 0

                            if has_bwce_to_check or has_flogo_to_check:
                                print("\n" + "="*60)
                                print("[STEP 9.9] Check Capability Status")
                                print("="*60)

                                # Wait for capabilities to initialize
                                import time
                                initial_wait = combined_check_config.get('initial_wait_seconds', 15)
                                print(f"[*] Waiting {initial_wait} seconds for capabilities to initialize...")
                                time.sleep(initial_wait)

                                # Check BWCE capabilities
                                if has_bwce_to_check:
                                    print(f"\n[*] Checking status for {len(bwce_results)} BWCE capability(ies)...")
                                    for bwce_result in bwce_results:
                                        if not bwce_result.get('capability_instance_id'):
                                            continue

                                        # Find the dataplane_id for this result
                                        dp_name = bwce_result.get('dataplane_name')
                                        dp_id = None
                                        for dp_result in all_results:
                                            if dp_result.get('name') == dp_name:
                                                dp_id = dp_result.get('dataplane_id')
                                                break

                                        if not dp_id:
                                            print(f"[!] Could not find dataplane ID for {dp_name}")
                                            continue

                                        cap_id = bwce_result.get('capability_instance_id')

                                        print(f"\n[*] Checking BWCE on {dp_name}...")
                                        status_result = new_user_service.check_bwce_capability_status(
                                            dp_id, cap_id,
                                            max_wait_seconds=combined_check_config.get('max_wait_seconds', 300),
                                            poll_interval_seconds=combined_check_config.get('poll_interval_seconds', 15)
                                        )

                                        capability_status_results[cap_id] = {
                                            'type': 'BWCE',
                                            'dataplane_id': dp_id,
                                            'dataplane_name': dp_name,
                                            'result': status_result
                                        }

                                        # Update bwce_result with status
                                        bwce_result['status_checked'] = True
                                        bwce_result['success'] = status_result.get('success')
                                        bwce_result['status'] = status_result.get('status')
                                        bwce_result['elapsed_time'] = status_result.get('elapsed_time', 0)

                                # Check Flogo capabilities
                                if has_flogo_to_check:
                                    print(f"\n[*] Checking status for {len(flogo_results)} Flogo capability(ies)...")
                                    for flogo_result in flogo_results:
                                        if not flogo_result.get('capability_instance_id'):
                                            continue

                                        # Find the dataplane_id for this result
                                        dp_name = flogo_result.get('dataplane_name')
                                        dp_id = None
                                        for dp_result in all_results:
                                            if dp_result.get('name') == dp_name:
                                                dp_id = dp_result.get('dataplane_id')
                                                break

                                        if not dp_id:
                                            print(f"[!] Could not find dataplane ID for {dp_name}")
                                            continue

                                        cap_id = flogo_result.get('capability_instance_id')

                                        print(f"\n[*] Checking Flogo on {dp_name}...")
                                        status_result = new_user_service.check_flogo_capability_status(
                                            dp_id, cap_id,
                                            max_wait_seconds=combined_check_config.get('max_wait_seconds', 300),
                                            poll_interval_seconds=combined_check_config.get('poll_interval_seconds', 15)
                                        )

                                        capability_status_results[cap_id] = {
                                            'type': 'FLOGO',
                                            'dataplane_id': dp_id,
                                            'dataplane_name': dp_name,
                                            'result': status_result
                                        }

                                        # Update flogo_result with status
                                        flogo_result['status_checked'] = True
                                        flogo_result['success'] = status_result.get('success')
                                        flogo_result['status'] = status_result.get('status')
                                        flogo_result['elapsed_time'] = status_result.get('elapsed_time', 0)

                            # Print combined summary
                            print(f"\n{'='*60}")
                            print(f"[*] Combined Capability Status Summary:")
                            print(f"{'='*60}")

                            if has_bwce_to_check:
                                green_bwce_count = sum(1 for r in bwce_results if r.get('success'))
                                print(f"    BWCE: {green_bwce_count}/{len(bwce_results)} green")
                                for result in bwce_results:
                                    status_emoji = "[+]" if result.get('success') else "[!]"
                                    print(f"      {status_emoji} {result.get('dataplane_name')}: {result.get('status', 'unknown').upper()}")

                            if has_flogo_to_check:
                                green_flogo_count = sum(1 for r in flogo_results if r.get('success'))
                                print(f"    Flogo: {green_flogo_count}/{len(flogo_results)} green")
                                for result in flogo_results:
                                    status_emoji = "[+]" if result.get('success') else "[!]"
                                    print(f"      {status_emoji} {result.get('dataplane_name')}: {result.get('status', 'unknown').upper()}")

                            print(f"{'='*60}\n")

                            summary["Check Capability Status"] = f"Pass ({len([r for r in capability_status_results.values() if r['result'].get('success')])}/{len(capability_status_results)} green)"

                        # Step 10: Deploy Applications (check both BWCE and Flogo results)
                        # Initialize variables to avoid undefined errors
                        if 'successful_bwce' not in locals():
                            successful_bwce = []
                        if 'successful_flogo' not in locals():
                            successful_flogo = []

                        if len(successful_bwce) > 0 or len(successful_flogo) > 0:
                            app_deployment_config = config.get('app_deployment_config', {})

                            if app_deployment_config.get('enabled', False):
                                print("\n" + "="*60)
                                print("[STEP 10] Deploy Applications")
                                print("="*60)

                                try:
                                    # Get resource names from config
                                    resources_config = config.get('dataplane_resources_config', {})
                                    storage_name = resources_config.get('storage', {}).get('name', 'dpstorage')
                                    ingress_name = resources_config.get('ingress', {}).get('name', 'dpingress')

                                    app_results = {
                                        "bwce_apps": [],
                                        "flogo_apps": []
                                    }

                                    # Get list of successfully provisioned dataplanes with green BWCE
                                    green_dataplanes = []
                                    for result in successful_bwce:
                                        dp_name = result.get('dataplane_name')
                                        dp_id = None
                                        # Find dataplane ID from all_results
                                        for dp_result in all_results:
                                            if dp_result.get('name') == dp_name:
                                                dp_id = dp_result.get('dataplane_id')
                                                break
                                        if dp_id:
                                            green_dataplanes.append({
                                                'name': dp_name,
                                                'id': dp_id
                                            })

                                    print(f"[*] Found {len(green_dataplanes)} dataplane(s) with green BWCE capability")

                                    # Deploy BWCE applications
                                    bwce_apps = app_deployment_config.get('bwce_apps', [])
                                    if bwce_apps:
                                        print(f"\n{'='*60}")
                                        print(f"[*] Deploying {len(bwce_apps)} BWCE Application(s)")
                                        print(f"{'='*60}")

                                        # Track which dataplanes have BWCE plugins checked/provisioned
                                        dataplanes_with_bwce_plugins = set()

                                        for app in bwce_apps:
                                            app_name = app.get('app_name')
                                            deploy_to = app.get('deploy_to_dataplanes', [])

                                            for dp_name in deploy_to:
                                                # Find matching green dataplane
                                                dp = next((d for d in green_dataplanes if d['name'] == dp_name), None)

                                                if not dp:
                                                    print(f"\n[*] Skipping {app_name} on {dp_name} - not green or not found")
                                                    app_results["bwce_apps"].append({
                                                        "app_name": app_name,
                                                        "dataplane": dp_name,
                                                        "success": False,
                                                        "error": "Dataplane not green"
                                                    })
                                                    continue

                                                # Provision BWCE buildtype if not already done for this dataplane
                                                if dp['id'] not in dataplanes_with_bwce_plugins:
                                                    print(f"\n[*] Checking/provisioning BWCE buildtype for dataplane: {dp_name}")

                                                    # Find the BWCE capability ID for this dataplane
                                                    bwce_capability_id = None
                                                    for bwce_result in successful_bwce:
                                                        if bwce_result.get('dataplane_name') == dp_name:
                                                            bwce_capability_id = bwce_result.get('capability_instance_id')
                                                            break

                                                    if bwce_capability_id:
                                                        buildtype_result = new_user_service.provision_bwce_buildtype(
                                                            dp['id'],
                                                            bwce_capability_id,
                                                            version="6.12.0-HF1"
                                                        )

                                                        if buildtype_result.get('success'):
                                                            dataplanes_with_bwce_plugins.add(dp['id'])
                                                            print(f"[+] BWCE buildtype ready for {dp_name}")
                                                        else:
                                                            print(f"[!] Warning: BWCE buildtype provisioning had issues for {dp_name}: {buildtype_result.get('error')}")
                                                            # Continue anyway - buildtype may already be provisioned
                                                            dataplanes_with_bwce_plugins.add(dp['id'])

                                                # Prepare app config
                                                app_config = {
                                                    "app_file_name": app.get('app_file_name'),
                                                    "app_name": app_name,
                                                    "app_folder": app_deployment_config.get('app_folder', 'apps_to_deploy'),
                                                    "make_public": app.get('make_public', False),
                                                    "scale_instances": app.get('scale_instances', 1),
                                                    "storage_name": storage_name,
                                                    "ingress_name": ingress_name
                                                }

                                                # Find BWCE capability ID for deployment
                                                for bwce_result in successful_bwce:
                                                    if bwce_result.get('dataplane_name') == dp_name:
                                                        app_config['capability_id'] = bwce_result.get('capability_instance_id')
                                                        break

                                                # Deploy
                                                result = new_user_service.deploy_bwce_app(dp['id'], dp_name, app_config)
                                                app_results["bwce_apps"].append({
                                                    "app_name": app_name,
                                                    "dataplane": dp_name,
                                                    "success": result.get('success'),
                                                    "build_id": result.get('build_id'),
                                                    "app_id": result.get('app_id'),  # Capture app_id
                                                    "error": result.get('error')
                                                })

                                    # Deploy Flogo applications (use Flogo capability results, not BWCE)
                                    flogo_apps = app_deployment_config.get('flogo_apps', [])
                                    if flogo_apps and 'successful_flogo' in locals() and len(successful_flogo) > 0:
                                        # Get list of dataplanes with green Flogo capability
                                        flogo_green_dataplanes = []
                                        for result in successful_flogo:
                                            dp_name = result.get('dataplane_name')
                                            dp_id = None
                                            # Find dataplane ID from all_results
                                            for dp_result in all_results:
                                                if dp_result.get('name') == dp_name:
                                                    dp_id = dp_result.get('dataplane_id')
                                                    break
                                            if dp_id:
                                                flogo_green_dataplanes.append({
                                                    'name': dp_name,
                                                    'id': dp_id,
                                                    'capability_id': result.get('capability_instance_id')
                                                })

                                        print(f"\n[*] Found {len(flogo_green_dataplanes)} dataplane(s) with green Flogo capability")

                                        print(f"\n{'='*60}")
                                        print(f"[*] Deploying {len(flogo_apps)} Flogo Application(s)")
                                        print(f"{'='*60}")

                                        # Track which dataplanes have connectors provisioned
                                        dataplanes_with_connectors = set()

                                        for app in flogo_apps:
                                            app_name = app.get('app_name')
                                            deploy_to = app.get('deploy_to_dataplanes', [])

                                            for dp_name in deploy_to:
                                                # Find matching green dataplane with Flogo capability
                                                dp = next((d for d in flogo_green_dataplanes if d['name'] == dp_name), None)

                                                if not dp:
                                                    print(f"\n[*] Skipping {app_name} on {dp_name} - Flogo capability not green or not found")
                                                    app_results["flogo_apps"].append({
                                                        "app_name": app_name,
                                                        "dataplane": dp_name,
                                                        "success": False,
                                                        "error": "Flogo capability not green"
                                                    })
                                                    continue

                                                # Provision buildtype and connectors if not already done for this dataplane
                                                if dp['id'] not in dataplanes_with_connectors:
                                                    print(f"\n[*] Provisioning Flogo prerequisites for dataplane: {dp_name}")

                                                    # Step 1: Provision Flogo buildtype (runtime templates)
                                                    print(f"[*] Step 1: Provisioning Flogo buildtype...")
                                                    from deploy_rest_api import RestApiDeployer
                                                    deployer = RestApiDeployer(new_user_service.session, new_user_service.auth.host_idm)

                                                    buildtype_result = deployer.provision_flogo_buildtype(
                                                        dp['id'],
                                                        dp['capability_id'],
                                                        version="2.26.1-b357"
                                                    )

                                                    if not buildtype_result.get('success'):
                                                        print(f"[!] Failed to provision Flogo buildtype for {dp_name}: {buildtype_result.get('error')}")
                                                        app_results["flogo_apps"].append({
                                                            "app_name": app_name,
                                                            "dataplane": dp_name,
                                                            "success": False,
                                                            "error": f"Buildtype provisioning failed: {buildtype_result.get('error')}"
                                                        })
                                                        continue

                                                    # Step 2: Provision connectors
                                                    print(f"[*] Step 2: Provisioning Flogo connectors...")

                                                    # Get the connectors required for this app
                                                    required_connectors = app.get('contrib_names', ['General'])

                                                    connector_result = deployer.provision_flogo_connectors(
                                                        dp['id'],
                                                        dp['capability_id'],
                                                        required_connectors
                                                    )

                                                    if connector_result.get('success'):
                                                        dataplanes_with_connectors.add(dp['id'])
                                                        print(f"[+] Flogo prerequisites provisioned successfully for {dp_name}")
                                                    else:
                                                        print(f"[!] Warning: Connector provisioning had issues for {dp_name}: {connector_result.get('error')}")
                                                        # Don't fail deployment if connectors have issues
                                                        dataplanes_with_connectors.add(dp['id'])

                                                # Prepare app config
                                                app_config = {
                                                    "app_file_name": app.get('app_file_name'),
                                                    "app_name": app_name,
                                                    "app_folder": app_deployment_config.get('app_folder', 'apps_to_deploy'),
                                                    "build_name": app.get('build_name', app_name),
                                                    "contrib_names": app.get('contrib_names', ['General']),
                                                    "tags": app.get('tags', []),
                                                    "make_public": app.get('make_public', False),
                                                    "scale_instances": app.get('scale_instances', 1),
                                                    "enable_service_mesh": app.get('enable_service_mesh', False),
                                                    "storage_name": storage_name,
                                                    "ingress_name": ingress_name,
                                                    "capability_id": dp.get('capability_id')  # Flogo capability ID from successful_flogo
                                                }

                                                # Verify capability_id is present
                                                if not app_config.get('capability_id'):
                                                    print(f"[!] Error: No Flogo capability_id found for {dp_name}")
                                                    app_results["flogo_apps"].append({
                                                        "app_name": app_name,
                                                        "dataplane": dp_name,
                                                        "success": False,
                                                        "error": "No capability_id provided"
                                                    })
                                                    continue

                                                # Deploy
                                                result = new_user_service.deploy_flogo_app(dp['id'], dp_name, app_config)
                                                app_results["flogo_apps"].append({
                                                    "app_name": app_name,
                                                    "dataplane": dp_name,
                                                    "success": result.get('success'),
                                                    "build_id": result.get('build_id'),
                                                    "app_id": result.get('app_id'),  # Capture app_id
                                                    "error": result.get('error')
                                                })
                                    elif flogo_apps:
                                        print(f"\n[*] Skipping Flogo application deployment (no green Flogo capabilities)")
                                        summary["Deploy Flogo Applications"] = "Skipped (No green Flogo capabilities)"

                                    # Print deployment summary
                                    print(f"\n{'='*60}")
                                    print(f"[*] Application Deployment Summary:")
                                    print(f"{'='*60}")

                                    bwce_success = sum(1 for r in app_results["bwce_apps"] if r.get('success'))
                                    bwce_total = len(app_results["bwce_apps"])
                                    flogo_success = sum(1 for r in app_results["flogo_apps"] if r.get('success'))
                                    flogo_total = len(app_results["flogo_apps"])

                                    print(f"    BWCE Apps: {bwce_success}/{bwce_total} successful")
                                    for result in app_results["bwce_apps"]:
                                        status_emoji = "[+]" if result.get('success') else "[!]"
                                        print(f"      {status_emoji} {result['app_name']} on {result['dataplane']}")
                                        if not result.get('success') and result.get('error'):
                                            print(f"          Error: {result['error']}")

                                    print(f"\n    Flogo Apps: {flogo_success}/{flogo_total} successful")
                                    for result in app_results["flogo_apps"]:
                                        status_emoji = "[+]" if result.get('success') else "[!]"
                                        print(f"      {status_emoji} {result['app_name']} on {result['dataplane']}")
                                        if not result.get('success') and result.get('error'):
                                            print(f"          Error: {result['error']}")

                                    print(f"{'='*60}\n")

                                    # Save deployed app information to file for later use
                                    try:
                                        deployed_apps_data = {
                                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                            "tenant_host": new_user_service.auth.host_idm,
                                            "bwce_apps": [],
                                            "flogo_apps": []
                                        }

                                        # Save BWCE app info with capability IDs
                                        for result in app_results["bwce_apps"]:
                                            if result.get('success') and result.get('app_id'):
                                                # Find capability ID
                                                capability_id = None
                                                for bwce_result in successful_bwce:
                                                    if bwce_result.get('dataplane_name') == result['dataplane']:
                                                        capability_id = bwce_result.get('capability_instance_id')
                                                        break

                                                # Find dataplane ID
                                                dp_id = None
                                                for dp_result in all_results:
                                                    if dp_result.get('name') == result['dataplane']:
                                                        dp_id = dp_result.get('dataplane_id')
                                                        break

                                                deployed_apps_data["bwce_apps"].append({
                                                    "app_name": result['app_name'],
                                                    "app_id": result['app_id'],
                                                    "dataplane_name": result['dataplane'],
                                                    "dataplane_id": dp_id,
                                                    "capability_id": capability_id,
                                                    "build_id": result.get('build_id')
                                                })

                                        # Save Flogo app info with capability IDs
                                        for result in app_results["flogo_apps"]:
                                            if result.get('success') and result.get('app_id'):
                                                # Find capability ID
                                                capability_id = None
                                                for flogo_result in successful_flogo:
                                                    if flogo_result.get('dataplane_name') == result['dataplane']:
                                                        capability_id = flogo_result.get('capability_instance_id')
                                                        break

                                                # Find dataplane ID
                                                dp_id = None
                                                for dp_result in all_results:
                                                    if dp_result.get('name') == result['dataplane']:
                                                        dp_id = dp_result.get('dataplane_id')
                                                        break

                                                deployed_apps_data["flogo_apps"].append({
                                                    "app_name": result['app_name'],
                                                    "app_id": result['app_id'],
                                                    "dataplane_name": result['dataplane'],
                                                    "dataplane_id": dp_id,
                                                    "capability_id": capability_id,
                                                    "build_id": result.get('build_id')
                                                })

                                        # Save to file
                                        with open('deployed_apps.json', 'w') as f:
                                            json.dump(deployed_apps_data, f, indent=2)
                                        print(f"[+] Deployed app information saved to: deployed_apps.json")

                                    except Exception as e:
                                        print(f"[!] Warning: Could not save deployed app information: {e}")

                                    # Step 10.5: Start Applications (if configured)
                                    if app_deployment_config.get('start_after_deploy', False):
                                        print(f"\n{'='*60}")
                                        print("[STEP 10.5] Start Applications")
                                        print(f"{'='*60}")

                                        try:
                                            start_results = {
                                                "bwce_apps": [],
                                                "flogo_apps": []
                                            }

                                            # Start BWCE applications
                                            for result in app_results["bwce_apps"]:
                                                if result.get('success') and result.get('app_id'):
                                                    app_name = result['app_name']
                                                    app_id = result['app_id']
                                                    dp_name = result['dataplane']

                                                    # Find dataplane and capability info
                                                    dp_id = None
                                                    capability_id = None
                                                    for dp_result in all_results:
                                                        if dp_result.get('name') == dp_name:
                                                            dp_id = dp_result.get('dataplane_id')
                                                            break

                                                    for bwce_result in successful_bwce:
                                                        if bwce_result.get('dataplane_name') == dp_name:
                                                            capability_id = bwce_result.get('capability_instance_id')
                                                            break

                                                    if dp_id and capability_id:
                                                        print(f"\n[*] Starting BWCE app: {app_name} on {dp_name}")
                                                        start_result = new_user_service.start_bwce_application(
                                                            dp_id,
                                                            capability_id,
                                                            app_id,
                                                            namespace='mydp-ns',
                                                            replicas=1
                                                        )

                                                        start_results["bwce_apps"].append({
                                                            "app_name": app_name,
                                                            "dataplane": dp_name,
                                                            "success": start_result.get('success'),
                                                            "error": start_result.get('error')
                                                        })
                                                    else:
                                                        print(f"[!] Cannot start {app_name} - missing dataplane or capability info")

                                            # Start Flogo applications
                                            for result in app_results["flogo_apps"]:
                                                if result.get('success') and result.get('app_id'):
                                                    app_name = result['app_name']
                                                    app_id = result['app_id']
                                                    dp_name = result['dataplane']

                                                    # Find dataplane and capability info
                                                    dp_id = None
                                                    capability_id = None
                                                    for dp_result in all_results:
                                                        if dp_result.get('name') == dp_name:
                                                            dp_id = dp_result.get('dataplane_id')
                                                            break

                                                    for flogo_result in successful_flogo:
                                                        if flogo_result.get('dataplane_name') == dp_name:
                                                            capability_id = flogo_result.get('capability_instance_id')
                                                            break

                                                    if dp_id and capability_id:
                                                        print(f"\n[*] Starting Flogo app: {app_name} on {dp_name}")
                                                        start_result = new_user_service.start_flogo_application(
                                                            dp_id,
                                                            capability_id,
                                                            app_id,
                                                            namespace='mydp-ns',
                                                            replicas=1
                                                        )

                                                        start_results["flogo_apps"].append({
                                                            "app_name": app_name,
                                                            "dataplane": dp_name,
                                                            "success": start_result.get('success'),
                                                            "error": start_result.get('error')
                                                        })
                                                    else:
                                                        print(f"[!] Cannot start {app_name} - missing dataplane or capability info")

                                            # Print start summary
                                            print(f"\n{'='*60}")
                                            print(f"[*] Application Start Summary:")
                                            print(f"{'='*60}")

                                            bwce_start_success = sum(1 for r in start_results["bwce_apps"] if r.get('success'))
                                            bwce_start_total = len(start_results["bwce_apps"])
                                            flogo_start_success = sum(1 for r in start_results["flogo_apps"] if r.get('success'))
                                            flogo_start_total = len(start_results["flogo_apps"])

                                            print(f"    BWCE Apps: {bwce_start_success}/{bwce_start_total} started")
                                            for result in start_results["bwce_apps"]:
                                                status_emoji = "[+]" if result.get('success') else "[!]"
                                                print(f"      {status_emoji} {result['app_name']} on {result['dataplane']}")
                                                if not result.get('success') and result.get('error'):
                                                    print(f"          Error: {result['error']}")

                                            print(f"\n    Flogo Apps: {flogo_start_success}/{flogo_start_total} started")
                                            for result in start_results["flogo_apps"]:
                                                status_emoji = "[+]" if result.get('success') else "[!]"
                                                print(f"      {status_emoji} {result['app_name']} on {result['dataplane']}")
                                                if not result.get('success') and result.get('error'):
                                                    print(f"          Error: {result['error']}")

                                            print(f"{'='*60}\n")

                                            # Update summary for start operations
                                            if bwce_start_total > 0:
                                                if bwce_start_success == bwce_start_total:
                                                    summary["Start BWCE Applications"] = f"Pass ({bwce_start_success}/{bwce_start_total})"
                                                elif bwce_start_success > 0:
                                                    summary["Start BWCE Applications"] = f"Partial ({bwce_start_success}/{bwce_start_total})"
                                                else:
                                                    summary["Start BWCE Applications"] = "Fail"

                                            if flogo_start_total > 0:
                                                if flogo_start_success == flogo_start_total:
                                                    summary["Start Flogo Applications"] = f"Pass ({flogo_start_success}/{flogo_start_total})"
                                                elif flogo_start_success > 0:
                                                    summary["Start Flogo Applications"] = f"Partial ({flogo_start_success}/{flogo_start_total})"
                                                else:
                                                    summary["Start Flogo Applications"] = "Fail"

                                        except Exception as e:
                                            print(f"[!] Application Start Error: {e}")
                                            import traceback
                                            traceback.print_exc()
                                            summary["Start BWCE Applications"] = "Error"
                                            summary["Start Flogo Applications"] = "Error"

                                    # Update summary - Track BWCE and Flogo separately

                                    # Update BWCE Apps summary
                                    if bwce_total == 0:
                                        summary["Deploy BWCE Applications"] = "Skipped (No apps configured)"
                                    elif bwce_success == bwce_total:
                                        summary["Deploy BWCE Applications"] = f"Pass ({bwce_success}/{bwce_total})"
                                    elif bwce_success > 0:
                                        summary["Deploy BWCE Applications"] = f"Partial ({bwce_success}/{bwce_total})"
                                    else:
                                        summary["Deploy BWCE Applications"] = "Fail"

                                    # Update Flogo Apps summary
                                    if flogo_total == 0:
                                        summary["Deploy Flogo Applications"] = "Skipped (No apps configured)"
                                    elif flogo_success == flogo_total:
                                        summary["Deploy Flogo Applications"] = f"Pass ({flogo_success}/{flogo_total})"
                                    elif flogo_success > 0:
                                        summary["Deploy Flogo Applications"] = f"Partial ({flogo_success}/{flogo_total})"
                                    else:
                                        summary["Deploy Flogo Applications"] = "Fail"

                                except Exception as e:
                                    print(f"[!] Application Deployment Error: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    summary["Deploy BWCE Applications"] = "Error"
                                    summary["Deploy Flogo Applications"] = "Error"
                            else:
                                summary["Deploy BWCE Applications"] = "Skipped (Disabled in config)"
                                summary["Deploy Flogo Applications"] = "Skipped (Disabled in config)"
                                print("\n[*] Application deployment is disabled in config.json")

                else:
                    summary["Provision BWCE Capability"] = "Skipped (Disabled in config)"
                    summary["Provision Flogo Capability"] = "Skipped (BWCE disabled)"
                    summary["Deploy BWCE Applications"] = "Skipped (BWCE disabled)"
                    summary["Deploy Flogo Applications"] = "Skipped (BWCE disabled)"
                    print("[*] BWCE provisioning is disabled in config.json")

            # Print per-prefix summary
            print_summary(summary)

def print_summary(summary):
    print("\n" + "="*40)
    print("       EXECUTION SUMMARY")
    print("="*40)
    for step, status in summary.items():
        dots = "." * (30 - len(step))
        print(f"{step} {dots} {status}")
    print("="*40 + "\n")

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='CP Automation - User Invitation Workflow')
    parser.add_argument('--config', type=str, default='config.json',
                      help='Configuration file path (default: config.json)')

    args = parser.parse_args()

    # Run user invitation workflow
    print("[*] Running User Invitation Workflow...")
    main()
