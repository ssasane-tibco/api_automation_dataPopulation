# ============================================================
# TIBCO Platform CP API Automation - Setup Script (Windows)
# ============================================================
# This script installs all required dependencies for the automation framework
# Run this script with PowerShell as Administrator (if needed)
# Usage: .\setup.ps1
# ============================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "TIBCO Platform CP API Automation - Setup Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Function to check if a command exists
function Test-CommandExists {
    param($command)
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = 'stop'
    try {
        if (Get-Command $command) { return $true }
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $oldPreference
    }
}

# Check Python installation
Write-Host "[*] Checking Python installation..." -ForegroundColor Yellow
if (Test-CommandExists python) {
    $pythonVersion = python --version 2>&1
    Write-Host "[+] Python is installed: $pythonVersion" -ForegroundColor Green

    # Check Python version (should be 3.7+)
    $versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
    if ($versionMatch) {
        $majorVersion = [int]$matches[1]
        $minorVersion = [int]$matches[2]

        if ($majorVersion -lt 3 -or ($majorVersion -eq 3 -and $minorVersion -lt 7)) {
            Write-Host "[!] WARNING: Python 3.7 or higher is recommended. Current version: Python $majorVersion.$minorVersion" -ForegroundColor Red
        }
    }
} else {
    Write-Host "[!] ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "[*] Please install Python 3.7 or higher from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "[*] Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    exit 1
}

# Check pip installation
Write-Host ""
Write-Host "[*] Checking pip installation..." -ForegroundColor Yellow
if (Test-CommandExists pip) {
    $pipVersion = pip --version 2>&1
    Write-Host "[+] pip is installed: $pipVersion" -ForegroundColor Green
} else {
    Write-Host "[!] ERROR: pip is not installed" -ForegroundColor Red
    Write-Host "[*] Installing pip..." -ForegroundColor Yellow
    python -m ensurepip --default-pip
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] Failed to install pip. Please install manually." -ForegroundColor Red
        exit 1
    }
}

# Upgrade pip to latest version
Write-Host ""
Write-Host "[*] Upgrading pip to latest version..." -ForegroundColor Yellow
python -m pip install --upgrade pip
if ($LASTEXITCODE -eq 0) {
    Write-Host "[+] pip upgraded successfully" -ForegroundColor Green
} else {
    Write-Host "[!] WARNING: Failed to upgrade pip, but continuing..." -ForegroundColor Yellow
}

# Check if requirements.txt exists
Write-Host ""
Write-Host "[*] Checking for requirements.txt..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    Write-Host "[+] requirements.txt found" -ForegroundColor Green
} else {
    Write-Host "[!] ERROR: requirements.txt not found in current directory" -ForegroundColor Red
    Write-Host "[*] Please run this script from the api_automation directory" -ForegroundColor Yellow
    exit 1
}

# Install Python dependencies
Write-Host ""
Write-Host "[*] Installing Python dependencies from requirements.txt..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
pip install -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "[+] All Python dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "[!] ERROR: Failed to install some dependencies" -ForegroundColor Red
    Write-Host "[*] Please check the error messages above" -ForegroundColor Yellow
    exit 1
}

# Check kubectl (optional but recommended for dataplane operations)
Write-Host ""
Write-Host "[*] Checking kubectl installation (optional)..." -ForegroundColor Yellow
if (Test-CommandExists kubectl) {
    $kubectlVersion = kubectl version --client --short 2>&1
    Write-Host "[+] kubectl is installed: $kubectlVersion" -ForegroundColor Green
} else {
    Write-Host "[!] WARNING: kubectl is not installed" -ForegroundColor Yellow
    Write-Host "[*] kubectl is required for dataplane registration commands" -ForegroundColor Yellow
    Write-Host "[*] Install from: https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/" -ForegroundColor Yellow
}

# Check helm (optional but recommended for dataplane operations)
Write-Host ""
Write-Host "[*] Checking helm installation (optional)..." -ForegroundColor Yellow
if (Test-CommandExists helm) {
    $helmVersion = helm version --short 2>&1
    Write-Host "[+] helm is installed: $helmVersion" -ForegroundColor Green
} else {
    Write-Host "[!] WARNING: helm is not installed" -ForegroundColor Yellow
    Write-Host "[*] helm is required for dataplane registration commands" -ForegroundColor Yellow
    Write-Host "[*] Install from: https://helm.sh/docs/intro/install/" -ForegroundColor Yellow
}

# Check config.json
Write-Host ""
Write-Host "[*] Checking configuration file..." -ForegroundColor Yellow
if (Test-Path "config.json") {
    Write-Host "[+] config.json found" -ForegroundColor Green

    # Validate JSON
    try {
        $config = Get-Content "config.json" -Raw | ConvertFrom-Json
        Write-Host "[+] config.json is valid JSON" -ForegroundColor Green

        # Check for required fields
        $requiredFields = @("admin_host", "credentials", "dataplanes", "activation_server")
        $missingFields = @()

        foreach ($field in $requiredFields) {
            if (-not ($config.PSObject.Properties.Name -contains $field)) {
                $missingFields += $field
            }
        }

        if ($missingFields.Count -gt 0) {
            Write-Host "[!] WARNING: config.json is missing required fields:" -ForegroundColor Yellow
            foreach ($field in $missingFields) {
                Write-Host "    - $field" -ForegroundColor Yellow
            }
        } else {
            Write-Host "[+] config.json has all required fields" -ForegroundColor Green
        }
    } catch {
        Write-Host "[!] ERROR: config.json is not valid JSON" -ForegroundColor Red
        Write-Host "[*] Please check the configuration file for syntax errors" -ForegroundColor Yellow
    }
} else {
    Write-Host "[!] WARNING: config.json not found" -ForegroundColor Yellow
    Write-Host "[*] You will need to create config.json before running the automation" -ForegroundColor Yellow
    Write-Host "[*] See README.md for configuration details" -ForegroundColor Yellow
}

# Verify apps_to_deploy directory
Write-Host ""
Write-Host "[*] Checking application deployment directory..." -ForegroundColor Yellow
if (Test-Path "apps_to_deploy") {
    Write-Host "[+] apps_to_deploy directory exists" -ForegroundColor Green

    $bwcePath = "apps_to_deploy\bwce"
    $flogoPath = "apps_to_deploy\flogo"

    if (Test-Path $bwcePath) {
        $bwceCount = (Get-ChildItem $bwcePath -Filter "*.ear" | Measure-Object).Count
        Write-Host "[+] BWCE apps directory exists ($bwceCount .ear files found)" -ForegroundColor Green
    } else {
        Write-Host "[!] WARNING: apps_to_deploy\bwce directory not found" -ForegroundColor Yellow
    }

    if (Test-Path $flogoPath) {
        $flogoCount = (Get-ChildItem $flogoPath -Filter "*.flogo" | Measure-Object).Count
        Write-Host "[+] Flogo apps directory exists ($flogoCount .flogo files found)" -ForegroundColor Green
    } else {
        Write-Host "[!] WARNING: apps_to_deploy\flogo directory not found" -ForegroundColor Yellow
    }
} else {
    Write-Host "[!] WARNING: apps_to_deploy directory not found" -ForegroundColor Yellow
    Write-Host "[*] Creating apps_to_deploy directory structure..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "apps_to_deploy\bwce" -Force | Out-Null
    New-Item -ItemType Directory -Path "apps_to_deploy\flogo" -Force | Out-Null
    Write-Host "[+] Directory structure created" -ForegroundColor Green
}

# Display installed packages
Write-Host ""
Write-Host "[*] Verifying installed packages..." -ForegroundColor Yellow
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan
pip list | Select-String -Pattern "requests|beautifulsoup4|urllib3|selenium|webdriver-manager"
Write-Host "------------------------------------------------------------" -ForegroundColor Cyan

# Final summary
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "SETUP SUMMARY" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[+] Python: Installed" -ForegroundColor Green
Write-Host "[+] pip: Installed" -ForegroundColor Green
Write-Host "[+] Python Dependencies: Installed" -ForegroundColor Green

if (Test-CommandExists kubectl) {
    Write-Host "[+] kubectl: Installed" -ForegroundColor Green
} else {
    Write-Host "[!] kubectl: Not Installed (Optional)" -ForegroundColor Yellow
}

if (Test-CommandExists helm) {
    Write-Host "[+] helm: Installed" -ForegroundColor Green
} else {
    Write-Host "[!] helm: Not Installed (Optional)" -ForegroundColor Yellow
}

if (Test-Path "config.json") {
    Write-Host "[+] config.json: Found" -ForegroundColor Green
} else {
    Write-Host "[!] config.json: Not Found (Required)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "NEXT STEPS" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Configure config.json with your environment details" -ForegroundColor White
Write-Host "   - See APP_DEPLOYMENT_CONFIG_GUIDE.md for details" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Place your application files in:" -ForegroundColor White
Write-Host "   - BWCE apps: apps_to_deploy\bwce\" -ForegroundColor Gray
Write-Host "   - Flogo apps: apps_to_deploy\flogo\" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Run the automation:" -ForegroundColor White
Write-Host "   - Full flow: python main.py" -ForegroundColor Gray
Write-Host "   - Deploy apps only: python deploy_apps_only.py" -ForegroundColor Gray
Write-Host "   - Start/stop apps: python start_stop_apps.py" -ForegroundColor Gray
Write-Host ""
Write-Host "4. For more information, see:" -ForegroundColor White
Write-Host "   - README.md - Overview and usage" -ForegroundColor Gray
Write-Host "   - MAIN_PY_EXECUTION_FLOW.md - Detailed execution flow" -ForegroundColor Gray
Write-Host "   - APP_DEPLOYMENT_CONFIG_GUIDE.md - Configuration guide" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[+] Setup completed successfully!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

