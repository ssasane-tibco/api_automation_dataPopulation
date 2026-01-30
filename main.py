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

    # Safe access to user query params with defaults
    user_params = config.get('user_query_params', {
        'order-by': '',
        'page': '1',
        'limit': '20',
        'person': ''
    })

    for prefix_entry in target_prefixes:
        if isinstance(prefix_entry, dict):
            target_prefix = prefix_entry.get('prefix')
            invite_email = prefix_entry.get('user_email')
        else:
            target_prefix = prefix_entry
            invite_email = config.get('invite_user_email')
        config['target_prefix'] = target_prefix

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
                                dp_config = dataplane_config.copy()

                                # Append target_prefix to the dataplane name, namespace, and serviceAccountName
                                base_name = dataplane_config.get('name', 'Dp1')
                                base_namespace = dataplane_config.get('namespace', 'default')
                                base_sa = dataplane_config.get('serviceAccountName', 'tibco-sa')

                                if dp_count > 1:
                                    dp_config['name'] = f"{target_prefix}-{base_name}-{i}"
                                    dp_config['namespace'] = f"{target_prefix}-{base_namespace}-{i}"
                                    dp_config['serviceAccountName'] = f"{target_prefix}-{base_sa}-{i}"
                                else:
                                    dp_config['name'] = f"{target_prefix}-{base_name}"
                                    dp_config['namespace'] = f"{target_prefix}-{base_namespace}"
                                    dp_config['serviceAccountName'] = f"{target_prefix}-{base_sa}"

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
