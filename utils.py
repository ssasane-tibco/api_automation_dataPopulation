import json
import base64
import subprocess
import sys
import tempfile
import os

def generate_admin_relay_state(admin_host):
    """Dynamically creates the Admin RelayState JSON and encodes it to Base64."""
    state_obj = {
        "resumeURL": f"{admin_host}/",
        "tenantId": "ADMIN",
        "xidp": "ta"
    }
    json_str = json.dumps(state_obj, separators=(',', ':'))
    return base64.b64encode(json_str.encode()).decode()

def generate_tenant_relay_state(prefix):
    """Dynamically creates the RelayState JSON and encodes it to Base64."""
    host = f"https://{prefix.lower()}.cp1-my.localhost.dataplanes.pro"
    state_obj = {
        "tenantId": "TSC",
        "resumeURL": f"{host}/cp/app/home",
        "welcomeURL": f"{host}/home",
        "xidp": "ta"
    }
    json_str = json.dumps(state_obj, separators=(',', ':'))
    return base64.b64encode(json_str.encode()).decode()

def load_config(file_path='config.json'):
    """Loads project configuration from a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def execute_commands_sequentially(commands, working_dir=None, shell=True):
    """
    Execute a list of commands sequentially.

    Args:
        commands (list): List of command strings to execute
        working_dir (str): Working directory for command execution (optional)
        shell (bool): Whether to execute commands through shell

    Returns:
        dict: Execution results
            {
                "success": True/False,
                "total_commands": int,
                "executed": int,
                "failed": int,
                "results": [{"command": str, "returncode": int, "output": str, "error": str}, ...]
            }
    """
    if not commands:
        print("[!] No commands to execute")
        return {
            "success": False,
            "total_commands": 0,
            "executed": 0,
            "failed": 0,
            "results": []
        }

    print(f"\n{'='*60}")
    print(f"[*] Executing {len(commands)} commands sequentially")
    print(f"{'='*60}\n")

    results = []
    executed = 0
    failed = 0

    for idx, command in enumerate(commands, 1):
        print(f"[*] Command {idx}/{len(commands)}:")
        print(f"    {command[:100]}{'...' if len(command) > 100 else ''}")

        temp_file = None
        try:
            # Special handling for kubectl heredoc commands (bash heredoc syntax)
            if '<<EOF' in command and 'kubectl' in command:
                # Extract the YAML content between <<EOF and EOF
                import re
                match = re.search(r'<<EOF\s+(.*?)\s+EOF', command, re.DOTALL)
                if match:
                    yaml_content = match.group(1).strip()

                    # Write YAML to temporary file
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
                    temp_file.write(yaml_content)
                    temp_file.close()

                    # Replace heredoc with file reference
                    # Extract kubectl command before <<EOF and remove trailing " -" if present
                    kubectl_part = command.split('<<EOF')[0].strip()

                    # Remove trailing " -" (stdin indicator) if present
                    if kubectl_part.endswith(' -'):
                        kubectl_part = kubectl_part[:-2].strip()

                    # Add -f flag if not present
                    if ' -f' not in kubectl_part:
                        kubectl_part += ' -f'

                    command = f'{kubectl_part} {temp_file.name}'

                    print(f"    [*] Converted heredoc to file input: {temp_file.name}")

            # Execute command
            result = subprocess.run(
                command,
                shell=shell,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout per command
            )

            executed += 1

            command_result = {
                "command": command,
                "returncode": result.returncode,
                "output": result.stdout,
                "error": result.stderr
            }

            if result.returncode == 0:
                print(f"[+] Command {idx} completed successfully")
                if result.stdout:
                    print(f"    Output: {result.stdout[:200]}{'...' if len(result.stdout) > 200 else ''}")
            else:
                failed += 1
                print(f"[!] Command {idx} failed with return code {result.returncode}")
                if result.stderr:
                    print(f"    Error: {result.stderr[:200]}")

            results.append(command_result)

        except subprocess.TimeoutExpired:
            failed += 1
            print(f"[!] Command {idx} timed out after 5 minutes")
            results.append({
                "command": command,
                "returncode": -1,
                "output": "",
                "error": "Command timed out"
            })
        except Exception as e:
            failed += 1
            print(f"[!] Command {idx} execution error: {e}")
            results.append({
                "command": command,
                "returncode": -1,
                "output": "",
                "error": str(e)
            })
        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass

        print()  # Empty line between commands

    print(f"{'='*60}")
    print(f"[*] Execution Summary:")
    print(f"    Total: {len(commands)}")
    print(f"    Executed: {executed}")
    print(f"    Successful: {executed - failed}")
    print(f"    Failed: {failed}")
    print(f"{'='*60}\n")

    return {
        "success": failed == 0,
        "total_commands": len(commands),
        "executed": executed,
        "failed": failed,
        "results": results
    }

def save_commands_to_file(commands, filename="dataplane_commands.txt"):
    """
    Save commands to a text file for later execution.

    Args:
        commands (list): List of command strings
        filename (str): Output filename

    Returns:
        bool: True if saved successfully
    """
    try:
        with open(filename, 'w') as f:
            f.write(f"# Dataplane Installation Commands\n")
            f.write(f"# Generated: {json.dumps(commands)}\n")
            f.write(f"# Total commands: {len(commands)}\n\n")

            for idx, command in enumerate(commands, 1):
                f.write(f"# Command {idx}\n")
                f.write(f"{command}\n\n")

        print(f"[+] Commands saved to: {filename}")
        return True
    except Exception as e:
        print(f"[!] Failed to save commands: {e}")
        return False
