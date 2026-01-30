#!/bin/bash
# ============================================================
# TIBCO Platform API Automation - Setup Script (Linux/Mac)
# ============================================================
# This script installs all required dependencies for the automation framework
# Usage: ./setup.sh
# ============================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}TIBCO Platform CP API Automation - Setup Script${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Detect OS
OS_TYPE=""
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_TYPE="$ID"
fi

echo -e "${YELLOW}[*] Detected OS: ${OS_TYPE:-Unknown}${NC}"
echo ""

# Check Python installation
echo -e "${YELLOW}[*] Checking Python installation...${NC}"
if command_exists python3; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}[+] Python is installed: $PYTHON_VERSION${NC}"

    # Extract version numbers
    MAJOR_VERSION=$(echo "$PYTHON_VERSION" | cut -d' ' -f2 | cut -d'.' -f1)
    MINOR_VERSION=$(echo "$PYTHON_VERSION" | cut -d' ' -f2 | cut -d'.' -f2)

    if [ "$MAJOR_VERSION" -lt 3 ] || ([ "$MAJOR_VERSION" -eq 3 ] && [ "$MINOR_VERSION" -lt 7 ]); then
        echo -e "${RED}[!] WARNING: Python 3.7 or higher is recommended. Current version: Python $MAJOR_VERSION.$MINOR_VERSION${NC}"
    fi

    # Check if Python 3.12+ on Ubuntu (requires virtual environment)
    if [ "$MAJOR_VERSION" -eq 3 ] && [ "$MINOR_VERSION" -ge 12 ] && [[ "$OS_TYPE" == "ubuntu" || "$OS_TYPE" == "debian" ]]; then
        echo -e "${YELLOW}[!] NOTE: Python $MAJOR_VERSION.$MINOR_VERSION detected on Ubuntu/Debian${NC}"
        echo -e "${YELLOW}[*] Virtual environment is required due to PEP 668 restrictions${NC}"
    fi

    PYTHON_CMD="python3"
elif command_exists python; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo -e "${GREEN}[+] Python is installed: $PYTHON_VERSION${NC}"
    PYTHON_CMD="python"
else
    echo -e "${RED}[!] ERROR: Python is not installed${NC}"
    echo -e "${YELLOW}[*] Please install Python 3.7 or higher:${NC}"
    echo -e "${YELLOW}    - Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-venv${NC}"
    echo -e "${YELLOW}    - CentOS/RHEL: sudo yum install python3 python3-pip${NC}"
    echo -e "${YELLOW}    - macOS: brew install python3${NC}"
    exit 1
fi

# Check pip installation
echo ""
echo -e "${YELLOW}[*] Checking pip installation...${NC}"
if command_exists pip3; then
    PIP_VERSION=$(pip3 --version 2>&1)
    echo -e "${GREEN}[+] pip is installed: $PIP_VERSION${NC}"
    PIP_CMD="pip3"
elif command_exists pip; then
    PIP_VERSION=$(pip --version 2>&1)
    echo -e "${GREEN}[+] pip is installed: $PIP_VERSION${NC}"
    PIP_CMD="pip"
else
    echo -e "${RED}[!] ERROR: pip is not installed${NC}"
    echo -e "${YELLOW}[*] Installing pip...${NC}"

    # Check if we need python3-pip package
    if [[ "$OS_TYPE" == "ubuntu" || "$OS_TYPE" == "debian" ]]; then
        echo -e "${YELLOW}[*] On Ubuntu/Debian, install with: sudo apt-get install python3-pip python3-venv${NC}"
    fi

    $PYTHON_CMD -m ensurepip --default-pip
    if [ $? -ne 0 ]; then
        echo -e "${RED}[!] Failed to install pip. Please install manually.${NC}"
        exit 1
    fi
    PIP_CMD="pip3"
fi

# Check for python3-venv on Ubuntu/Debian
if [[ "$OS_TYPE" == "ubuntu" || "$OS_TYPE" == "debian" ]]; then
    echo ""
    echo -e "${YELLOW}[*] Checking python3-venv package...${NC}"
    if ! dpkg -l | grep -q python3-venv; then
        echo -e "${YELLOW}[!] python3-venv not found, attempting to install...${NC}"
        echo -e "${YELLOW}[*] You may need to run: sudo apt-get install python3-venv${NC}"
    else
        echo -e "${GREEN}[+] python3-venv is installed${NC}"
    fi
fi

# Check if requirements.txt exists
echo ""
echo -e "${YELLOW}[*] Checking for requirements.txt...${NC}"
if [ -f "requirements.txt" ]; then
    echo -e "${GREEN}[+] requirements.txt found${NC}"
else
    echo -e "${RED}[!] ERROR: requirements.txt not found in current directory${NC}"
    echo -e "${YELLOW}[*] Please run this script from the api_automation directory${NC}"
    exit 1
fi

# Create virtual environment
VENV_DIR="venv"
echo ""
echo -e "${YELLOW}[*] Checking for virtual environment...${NC}"
if [ -d "$VENV_DIR" ]; then
    echo -e "${GREEN}[+] Virtual environment already exists at $VENV_DIR${NC}"
else
    echo -e "${YELLOW}[*] Creating virtual environment at $VENV_DIR...${NC}"
    $PYTHON_CMD -m venv $VENV_DIR
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[+] Virtual environment created successfully${NC}"
    else
        echo -e "${RED}[!] ERROR: Failed to create virtual environment${NC}"
        echo -e "${YELLOW}[*] You may need to install python3-venv:${NC}"
        echo -e "${YELLOW}    sudo apt-get install python3-venv${NC}"
        exit 1
    fi
fi

# Activate virtual environment
echo ""
echo -e "${YELLOW}[*] Activating virtual environment...${NC}"
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    echo -e "${GREEN}[+] Virtual environment activated${NC}"

    # Update pip in virtual environment
    echo ""
    echo -e "${YELLOW}[*] Upgrading pip in virtual environment...${NC}"
    pip install --upgrade pip >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[+] pip upgraded successfully${NC}"
    else
        echo -e "${YELLOW}[!] WARNING: Failed to upgrade pip, but continuing...${NC}"
    fi

    PIP_CMD="pip"
else
    echo -e "${RED}[!] ERROR: Virtual environment activation script not found${NC}"
    exit 1
fi

# Install Python dependencies in virtual environment
echo ""
echo -e "${YELLOW}[*] Installing Python dependencies from requirements.txt...${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"
$PIP_CMD install -r requirements.txt
if [ $? -eq 0 ]; then
    echo -e "${CYAN}------------------------------------------------------------${NC}"
    echo -e "${GREEN}[+] All Python dependencies installed successfully!${NC}"
else
    echo -e "${CYAN}------------------------------------------------------------${NC}"
    echo -e "${RED}[!] ERROR: Failed to install some dependencies${NC}"
    echo -e "${YELLOW}[*] Please check the error messages above${NC}"
    exit 1
fi

# Check kubectl (optional but recommended for dataplane operations)
echo ""
echo -e "${YELLOW}[*] Checking kubectl installation (optional)...${NC}"
if command_exists kubectl; then
    KUBECTL_VERSION=$(kubectl version --client --short 2>&1 | head -n1)
    echo -e "${GREEN}[+] kubectl is installed: $KUBECTL_VERSION${NC}"
else
    echo -e "${YELLOW}[!] WARNING: kubectl is not installed${NC}"
    echo -e "${YELLOW}[*] kubectl is required for dataplane registration commands${NC}"
    echo -e "${YELLOW}[*] Install from: https://kubernetes.io/docs/tasks/tools/${NC}"
fi

# Check helm (optional but recommended for dataplane operations)
echo ""
echo -e "${YELLOW}[*] Checking helm installation (optional)...${NC}"
if command_exists helm; then
    HELM_VERSION=$(helm version --short 2>&1)
    echo -e "${GREEN}[+] helm is installed: $HELM_VERSION${NC}"
else
    echo -e "${YELLOW}[!] WARNING: helm is not installed${NC}"
    echo -e "${YELLOW}[*] helm is required for dataplane registration commands${NC}"
    echo -e "${YELLOW}[*] Install from: https://helm.sh/docs/intro/install/${NC}"
fi

# Check Google Chrome (required for Selenium automation)
echo ""
echo -e "${YELLOW}[*] Checking Google Chrome installation (required for user registration)...${NC}"
if command_exists google-chrome || command_exists google-chrome-stable || command_exists chromium-browser || command_exists chromium; then
    if command_exists google-chrome-stable; then
        CHROME_VERSION=$(google-chrome-stable --version 2>&1)
    elif command_exists google-chrome; then
        CHROME_VERSION=$(google-chrome --version 2>&1)
    elif command_exists chromium-browser; then
        CHROME_VERSION=$(chromium-browser --version 2>&1)
    else
        CHROME_VERSION=$(chromium --version 2>&1)
    fi
    echo -e "${GREEN}[+] Chrome/Chromium is installed: $CHROME_VERSION${NC}"
else
    echo -e "${RED}[!] WARNING: Google Chrome or Chromium is not installed${NC}"
    echo -e "${YELLOW}[*] Chrome is required for user registration and EULA acceptance${NC}"
    echo ""
    echo -e "${YELLOW}[*] Installation instructions:${NC}"
    if [[ "$OS_TYPE" == "ubuntu" || "$OS_TYPE" == "debian" ]]; then
        echo -e "${YELLOW}    Ubuntu/Debian:${NC}"
        echo -e "${CYAN}      wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb${NC}"
        echo -e "${CYAN}      sudo dpkg -i google-chrome-stable_current_amd64.deb${NC}"
        echo -e "${CYAN}      sudo apt-get install -f${NC}"
        echo -e "${YELLOW}    OR install Chromium:${NC}"
        echo -e "${CYAN}      sudo apt-get install chromium-browser${NC}"
    elif [[ "$OS_TYPE" == "centos" || "$OS_TYPE" == "rhel" || "$OS_TYPE" == "fedora" ]]; then
        echo -e "${YELLOW}    CentOS/RHEL/Fedora:${NC}"
        echo -e "${CYAN}      wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm${NC}"
        echo -e "${CYAN}      sudo yum localinstall google-chrome-stable_current_x86_64.rpm${NC}"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${YELLOW}    macOS:${NC}"
        echo -e "${CYAN}      brew install --cask google-chrome${NC}"
    fi
    echo ""
fi
# Check config.json
echo ""
echo -e "${YELLOW}[*] Checking configuration file...${NC}"
if [ -f "config.json" ]; then
    echo -e "${GREEN}[+] config.json found${NC}"

    # Validate JSON (requires jq or python)
    if command_exists jq; then
        if jq empty config.json >/dev/null 2>&1; then
            echo -e "${GREEN}[+] config.json is valid JSON${NC}"

            # Check for required fields
            REQUIRED_FIELDS=("admin_host" "credentials" "dataplanes" "activation_server")
            MISSING_FIELDS=()

            for field in "${REQUIRED_FIELDS[@]}"; do
                if ! jq -e ".$field" config.json >/dev/null 2>&1; then
                    MISSING_FIELDS+=("$field")
                fi
            done

            if [ ${#MISSING_FIELDS[@]} -gt 0 ]; then
                echo -e "${YELLOW}[!] WARNING: config.json is missing required fields:${NC}"
                for field in "${MISSING_FIELDS[@]}"; do
                    echo -e "${YELLOW}    - $field${NC}"
                done
            else
                echo -e "${GREEN}[+] config.json has all required fields${NC}"
            fi
        else
            echo -e "${RED}[!] ERROR: config.json is not valid JSON${NC}"
            echo -e "${YELLOW}[*] Please check the configuration file for syntax errors${NC}"
        fi
    elif command_exists python3; then
        if python3 -m json.tool config.json >/dev/null 2>&1; then
            echo -e "${GREEN}[+] config.json is valid JSON${NC}"
        else
            echo -e "${RED}[!] ERROR: config.json is not valid JSON${NC}"
            echo -e "${YELLOW}[*] Please check the configuration file for syntax errors${NC}"
        fi
    fi
else
    echo -e "${YELLOW}[!] WARNING: config.json not found${NC}"
    echo -e "${YELLOW}[*] You will need to create config.json before running the automation${NC}"
    echo -e "${YELLOW}[*] See README.md for configuration details${NC}"
fi

# Verify apps_to_deploy directory
echo ""
echo -e "${YELLOW}[*] Checking application deployment directory...${NC}"
if [ -d "apps_to_deploy" ]; then
    echo -e "${GREEN}[+] apps_to_deploy directory exists${NC}"

    if [ -d "apps_to_deploy/bwce" ]; then
        BWCE_COUNT=$(find apps_to_deploy/bwce -name "*.ear" 2>/dev/null | wc -l)
        echo -e "${GREEN}[+] BWCE apps directory exists ($BWCE_COUNT .ear files found)${NC}"
    else
        echo -e "${YELLOW}[!] WARNING: apps_to_deploy/bwce directory not found${NC}"
    fi

    if [ -d "apps_to_deploy/flogo" ]; then
        FLOGO_COUNT=$(find apps_to_deploy/flogo -name "*.flogo" 2>/dev/null | wc -l)
        echo -e "${GREEN}[+] Flogo apps directory exists ($FLOGO_COUNT .flogo files found)${NC}"
    else
        echo -e "${YELLOW}[!] WARNING: apps_to_deploy/flogo directory not found${NC}"
    fi
else
    echo -e "${YELLOW}[!] WARNING: apps_to_deploy directory not found${NC}"
    echo -e "${YELLOW}[*] Creating apps_to_deploy directory structure...${NC}"
    mkdir -p apps_to_deploy/bwce
    mkdir -p apps_to_deploy/flogo
    echo -e "${GREEN}[+] Directory structure created${NC}"
fi

# Make Python scripts executable
echo ""
echo -e "${YELLOW}[*] Making Python scripts executable...${NC}"
chmod +x *.py 2>/dev/null
echo -e "${GREEN}[+] Scripts are now executable${NC}"

# Display installed packages
echo ""
echo -e "${YELLOW}[*] Verifying installed packages...${NC}"
echo -e "${CYAN}------------------------------------------------------------${NC}"
$PIP_CMD list | grep -E "requests|beautifulsoup4|urllib3|selenium|webdriver-manager"
echo -e "${CYAN}------------------------------------------------------------${NC}"

# Final summary
echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}SETUP SUMMARY${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""
echo -e "${GREEN}[+] Python: Installed${NC}"
echo -e "${GREEN}[+] pip: Installed${NC}"
echo -e "${GREEN}[+] Python Dependencies: Installed${NC}"

if command_exists kubectl; then
    echo -e "${GREEN}[+] kubectl: Installed${NC}"
else
    echo -e "${YELLOW}[!] kubectl: Not Installed (Optional)${NC}"
fi

if command_exists helm; then
    echo -e "${GREEN}[+] helm: Installed${NC}"
else
    echo -e "${YELLOW}[!] helm: Not Installed (Optional)${NC}"
fi

if [ -f "config.json" ]; then
    echo -e "${GREEN}[+] config.json: Found${NC}"
else
    echo -e "${YELLOW}[!] config.json: Not Found (Required)${NC}"
fi

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}NEXT STEPS${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""
echo -e "1. ${GREEN}Activate the virtual environment (REQUIRED):${NC}"
echo -e "   ${CYAN}source venv/bin/activate${NC}"
echo -e "   ${YELLOW}(You MUST do this before running any scripts!)${NC}"
echo ""
echo -e "2. Configure config.json with your environment details"
echo -e "   ${CYAN}- See APP_DEPLOYMENT_CONFIG_GUIDE.md for details${NC}"
echo ""
echo -e "3. Place your application files in:"
echo -e "   ${CYAN}- BWCE apps: apps_to_deploy/bwce/${NC}"
echo -e "   ${CYAN}- Flogo apps: apps_to_deploy/flogo/${NC}"
echo ""
echo -e "4. Run the automation (inside activated venv):"
echo -e "   ${CYAN}- Full flow: python main.py${NC}"
echo -e "   ${CYAN}- Deploy apps only: python deploy_apps_only.py${NC}"
echo -e "   ${CYAN}- Start apps: python start_apps.py${NC}"
echo -e "   ${CYAN}- Start/stop apps: python start_stop_apps.py${NC}"
echo ""
if [[ "$OS_TYPE" == "ubuntu" || "$OS_TYPE" == "debian" ]]; then
    echo -e "   ${YELLOW}NOTE (Ubuntu/Debian): Use 'python' inside venv (not python3)${NC}"
    echo ""
fi
echo -e "5. For more information, see:"
echo -e "   ${CYAN}- README.md - Overview and usage${NC}"
echo -e "   ${CYAN}- UBUNTU_SETUP_GUIDE.md - Ubuntu-specific instructions${NC}"
echo -e "   ${CYAN}- MAIN_PY_EXECUTION_FLOW.md - Detailed execution flow${NC}"
echo -e "   ${CYAN}- APP_DEPLOYMENT_CONFIG_GUIDE.md - Configuration guide${NC}"
echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${GREEN}[+] Setup completed successfully!${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  IMPORTANT: Virtual Environment Activation${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  Before running ANY Python scripts, activate the venv:${NC}"
echo ""
echo -e "${CYAN}     source venv/bin/activate${NC}"
echo ""
echo -e "${YELLOW}  Then run scripts with:${NC}"
echo -e "${CYAN}     python main.py${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

