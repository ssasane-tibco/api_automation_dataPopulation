# TIBCO Control Plane Automation

Complete end-to-end automation for TIBCO Control Plane:
- User provisioning and invitation
- Dataplane registration and status monitoring
- BWCE and Flogo capability provisioning
- Application deployment (BWCE & Flogo)
- Application lifecycle management (start/stop/scale)

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[README.md](README.md)** | Main documentation with quick start and usage |
| **[INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)** | Complete installation and setup guide |
| **[UBUNTU_QUICK_START.md](UBUNTU_QUICK_START.md)** | ⚡ Quick reference for Ubuntu users |
| **[QUICK_FIX_UBUNTU.md](QUICK_FIX_UBUNTU.md)** | 🔧 Quick fix for common Ubuntu/Selenium issues |
| **[UBUNTU_SETUP_GUIDE.md](UBUNTU_SETUP_GUIDE.md)** | Ubuntu/Linux specific setup instructions |
| **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** | Complete project overview and architecture |
| **[MAIN_PY_EXECUTION_FLOW.md](MAIN_PY_EXECUTION_FLOW.md)** | Detailed workflow and execution flow |
| **[APP_DEPLOYMENT_CONFIG_GUIDE.md](APP_DEPLOYMENT_CONFIG_GUIDE.md)** | Application configuration reference |
| **[requirements.txt](requirements.txt)** | Python dependencies list |

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.8+** (Python 3.7+ supported)
- **pip** (Python package manager)
- **Google Chrome or Chromium** (required for user registration)
- **kubectl** (for dataplane operations)
- **helm 3.x** (for dataplane provisioning)

> **📌 Ubuntu/Debian Users:** See **[UBUNTU_QUICK_START.md](UBUNTU_QUICK_START.md)** for a one-page reference guide!

### Installing Google Chrome (Linux)

**Ubuntu/Debian:**
```bash
# Quick install (requires sudo)
sudo ./install_chrome_ubuntu.sh

# OR manual install
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f
```

**CentOS/RHEL:**
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
sudo yum localinstall google-chrome-stable_current_x86_64.rpm
```

### Automated Installation (Recommended)

**Windows (PowerShell):**
```powershell
.\setup.ps1
```

**Linux/Mac (Bash):**
```bash
chmod +x setup.sh
./setup.sh
```

> **📌 Ubuntu/Debian Users (Python 3.12+):**  
> The setup script automatically creates and activates a virtual environment to handle PEP 668 restrictions.
> See **[UBUNTU_SETUP_GUIDE.md](UBUNTU_SETUP_GUIDE.md)** for detailed Ubuntu 24.04+ specific instructions.

The setup script will:
- ✅ Verify Python and pip installation
- ✅ Create virtual environment (automatically on Linux/Mac)
- ✅ Install all required Python packages (including Selenium and ChromeDriver manager)
- ✅ Check kubectl and helm availability
- ✅ Validate config.json
- ✅ Create necessary directory structure

**IMPORTANT (Linux/Mac):** After running setup, activate the virtual environment:
```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt indicating the virtual environment is active.

### Manual Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Create application directories
mkdir -p apps_to_deploy/bwce
mkdir -p apps_to_deploy/flogo
```

### Configuration

1. Copy and configure `config.json` with your environment details
2. Place application files:
   - BWCE apps (`.ear` files) → `apps_to_deploy/bwce/`
   - Flogo apps (`.flogo` files) → `apps_to_deploy/flogo/`

See **[APP_DEPLOYMENT_CONFIG_GUIDE.md](APP_DEPLOYMENT_CONFIG_GUIDE.md)** for detailed configuration options.

### Run Complete Automation

```bash
python main.py
```

This will:
1. ✅ Login as admin
2. ✅ Provision subscription
3. ✅ Invite and register user
4. ✅ Register dataplanes
5. ✅ Execute installation commands
6. ✅ Check dataplane status (wait for GREEN)
7. ✅ Add activation server
8. ✅ Create storage and ingress resources
9. ✅ Provision BWCE capability

---

## 📋 Available Scripts

### 1. Full End-to-End Automation (`main.py`)
Complete workflow from user provisioning to application deployment.

```bash
python main.py
```

**Includes:**
- Admin login and subscription provisioning
- User invitation and registration
- Dataplane registration and status monitoring
- Activation server setup
- BWCE & Flogo capability provisioning
- Application deployment (BWCE & Flogo)
- Application lifecycle management (start/stop)

### 2. Deploy Applications Only (`deploy_apps_only.py`)
Deploy BWCE and Flogo applications to existing dataplanes.

```bash
python deploy_apps_only.py
```

**Prerequisites:**
- Tenant subscription exists
- User logged in and accepted invitation
- Dataplanes registered and green
- Capabilities provisioned and green

### 3. Start/Stop Applications (`start_stop_apps.py`)
Manage application lifecycle after deployment.

```bash
# Start applications
python start_stop_apps.py --action start

# Stop applications
python start_stop_apps.py --action stop

# Scale applications
python start_stop_apps.py --action scale --replicas 3
```

### 4. Start Applications (`start_apps.py`)
Simplified script to start deployed applications.

```bash
python start_apps.py
```

---

## 🔧 Configuration Reference

### Main Configuration (`config.json`)

```json
{
    "admin_host": "https://admin.cp1-my.localhost.dataplanes.pro",
    "target_prefix": "vedu5",
    "invite_user_email": "vedu5@tibco.com",
    
    "credentials": {
        "cp_admin_email": "cp-test@tibco.com",
        "cp_admin_password": "your-password",
        "invite_user_password": "your-password"
    },
    
    "dataplane_config": {
        "dpCount": 1,
        "name": "Dp-Auto-Test",
        "namespace": "mydp-ns",
        "serviceAccountName": "mydp-sa",
        "isFluentBitEnabled": true,
        "enableClusterScopedPerm": true
    },
    
    "dataplane_resources_config": {
        "create_resources": true,
        "storage": {
            "name": "dpstorage",
            "storage_class_name": "hostpath"
        },
        "ingress": {
            "name": "dpingress",
            "ingress_controller": "traefik",
            "ingress_class_name": "traefik",
            "fqdn": "python.localhost.dataplanes.pro"
        }
    },
    
    "activation_server_config": {
        "enabled": true,
        "url": "https://na1pcpfhelmcm01.tibco.com:7070",
        "version": "1.8.0"
    },
    
    "bwce_capability_config": {
        "enabled": true,
        "version": "1.5.0",
        "fluentbit_enabled": true
    },
    
    "flogo_capability_config": {
        "enabled": true,
        "version": "1.15.0",
        "fluentbit_enabled": true
    },
    
    "app_deployment_config": {
        "enabled": true,
        "start_after_deploy": true,
        "app_folder": "apps_to_deploy",
        "bwce_apps": [
            {
                "app_file_name": "BWCE_TimerLog.application.ear",
                "app_name": "BWCETimerLog",
                "make_public": false,
                "scale_instances": 1,
                "deploy_to_dataplanes": ["Dp-Auto-Test"]
            }
        ],
        "flogo_apps": [
            {
                "app_file_name": "flogofailureapp.flogo",
                "app_name": "FlogoFailureApp",
                "build_name": "FlogoFailureApp",
                "contrib_names": ["General"],
                "tags": [],
                "make_public": false,
                "scale_instances": 1,
                "enable_service_mesh": false,
                "deploy_to_dataplanes": ["Dp-Auto-Test"]
            }
        ]
    }
}
```

See **[APP_DEPLOYMENT_CONFIG_GUIDE.md](APP_DEPLOYMENT_CONFIG_GUIDE.md)** for detailed application configuration options.

---

## 📁 Project Structure

```
api_automation/
├── main.py                          # Main end-to-end automation script
├── deploy_apps_only.py              # Standalone app deployment
├── start_apps.py                    # Start deployed applications
├── start_stop_apps.py               # Application lifecycle management
├── auth.py                          # Authentication module
├── services.py                      # API service methods
├── utils.py                         # Utility functions
├── deploy_rest_api.py               # REST API deployment helper
├── config.json                      # Main configuration file
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── MAIN_PY_EXECUTION_FLOW.md        # Execution flow documentation
├── APP_DEPLOYMENT_CONFIG_GUIDE.md   # App deployment guide
└── apps_to_deploy/                  # Application files
    ├── bwce/                        # BWCE application EAR files
    └── flogo/                       # Flogo application files
```

---

## ✅ Execution Summary

When you run `python main.py`, the script executes these steps:

1. **Admin Login** - Authenticate as CP admin
2. **Provision Subscription** - Create tenant subscription
3. **Admin Logout** - Logout admin session
4. **CP Login** - Login to Control Plane
5. **Invite New User** - Send invitation to user email
6. **CP Logout** - Logout CP session
7. **Accept & Register User** - User accepts invitation (automated)
8. **Listing Users from CP** - Verify user creation
9. **New User Login Verification** - Confirm user can login
10. **Register Dataplanes** - Register Kubernetes dataplanes
11. **Add Activation Server** - Configure license server
12. **Link Activation Server** - Associate with dataplanes
13. **Check Dataplane Status** - Wait for GREEN status
14. **Provision BWCE Capability** - Install BWCE provisioner
15. **Provision Flogo Capability** - Install Flogo provisioner
16. **Check Capability Status** - Verify both GREEN
17. **Deploy BWCE Applications** - Deploy EAR files
18. **Deploy Flogo Applications** - Deploy Flogo apps
19. **Start BWCE Applications** - Scale to desired replicas
20. **Start Flogo Applications** - Scale to desired replicas

---

## 🔍 Monitoring and Verification

### Check Dataplane Status
```bash
kubectl get pods -n mydp-ns
```

### Check BWCE Applications
```bash
kubectl get pods -n mydp-ns -l app.kubernetes.io/component=bwce
```

### Check Flogo Applications
```bash
kubectl get pods -n mydp-ns -l app.kubernetes.io/component=flogo
```

### View Application Logs
```bash
# BWCE app logs
kubectl logs -n mydp-ns <bwce-pod-name>

# Flogo app logs
kubectl logs -n mydp-ns <flogo-pod-name>
```

---

## 🐛 Troubleshooting

### User Login Verification Fails (ATMOSPHERE-11004)
If you see "ATMOSPHERE-11004" error during user login verification:
- This is a **timing issue**, not a failure - the user IS registered successfully
- User permissions take 30-90 seconds to fully propagate through the system
- The script automatically retries 5 times with increasing wait times (15, 30, 45, 60 seconds)
- **Solution**: Simply run the script again, or manually verify the user can login at the tenant URL

### Login Issues
- Verify credentials in `config.json`
- Check network connectivity to admin/tenant hosts
- Ensure IDP service is accessible

### Dataplane Not Going Green
- Check `kubectl get pods -n mydp-ns`
- Verify helm commands executed successfully
- Check dataplane logs: `kubectl logs -n mydp-ns <pod-name>`

### Capability Provisioning Fails
- Ensure dataplane is GREEN
- Verify storage and ingress resources exist
- Check capability pod logs

### Application Deployment Fails
- Verify application files exist in `apps_to_deploy/`
- Check buildtype is provisioned
- For Flogo: ensure connectors are provisioned
- Verify sufficient resources in cluster

---

## 📝 Notes

- **Selenium WebDriver**: Required for accepting EULA during user registration
- **HAR Files**: Historical reference files (can be ignored)
- **Session Cookies**: Automatically managed by the scripts
- **CSRF Tokens**: Handled automatically
- **Build Types**: Auto-provisioned before first deployment

---

## 🐛 Troubleshooting

### Common Issues

**Installation Failures:**
- Run `python validate_setup.py` to check setup
- See [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) for detailed troubleshooting

**Selenium/WebDriver Issues (Accept & Register User fails):**

If you see `ModuleNotFoundError: No module named 'selenium'` or `'webdriver_manager'`:

```bash
# Make sure virtual environment is activated
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Install missing dependencies
pip install selenium==4.16.0 webdriver-manager==4.0.1

# Or reinstall all dependencies
pip install -r requirements.txt
```

**Chrome/ChromeDriver Issues:**
- Ensure Google Chrome is installed on your system
- The webdriver-manager package automatically downloads ChromeDriver
- If behind a proxy, configure proxy settings in environment variables

**Configuration Errors:**
- Verify `config.json` syntax with JSON validator
- Check all required fields in [APP_DEPLOYMENT_CONFIG_GUIDE.md](APP_DEPLOYMENT_CONFIG_GUIDE.md)

**Authentication Issues:**
- Verify credentials in `config.json`
- Check network access to Control Plane
- Review SAML authentication flow in logs

**Deployment Failures:**
- Ensure kubectl and helm are configured
- Verify cluster access
- Check dataplane status (must be GREEN)

For detailed troubleshooting, see:
- **[INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)** - Setup issues
- **[MAIN_PY_EXECUTION_FLOW.md](MAIN_PY_EXECUTION_FLOW.md)** - Execution flow and debugging

---

## 🤝 Contributing

For issues or improvements, please:
1. Check existing documentation
2. Verify configuration settings
3. Review execution logs
4. Contact the automation team

---

## 📄 License

Internal TIBCO use only.

---

**Last Updated**: January 2026
