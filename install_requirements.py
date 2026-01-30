#!/usr/bin/env python3
"""
install_requirements.py
Automates installation of required Python packages and Google Chrome for Windows and Linux.
"""
import os
import sys
import subprocess
import platform
import shutil
import venv
import glob

REQUIRED_PYTHON = (3, 12)
REQUIRED_PACKAGES = [
    "requests==2.31.0",
    "urllib3==2.0.7",
    "certifi>=2023.7.22",
    "charset-normalizer>=3.3.0",
    "idna>=3.4",
    "soupsieve>=2.5",
    "selenium==4.16.0",
    "webdriver-manager==4.0.1",
    "beautifulsoup4"
]

VENV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")


def check_python_version():
    if sys.version_info < REQUIRED_PYTHON:
        print(f"Python {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]} or higher is required.")
        print("Please install the required Python version and re-run this script.")
        sys.exit(1)
    else:
        print(f"Python version {sys.version_info.major}.{sys.version_info.minor} detected.")


def ensure_pip():
    """Ensure pip is installed in the current Python environment."""
    import importlib.util
    import tempfile
    import urllib.request
    import sys
    # Check if pip is available
    pip_spec = importlib.util.find_spec("pip")
    if pip_spec is not None:
        return  # pip is available
    print("pip not found. Attempting to install pip...")
    # Try ensurepip
    try:
        import ensurepip
        print("Installing pip using ensurepip...")
        ensurepip.bootstrap(upgrade=True)
        # After ensurepip, upgrade pip to latest
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        return
    except Exception as e:
        print(f"ensurepip failed: {e}")
    # Fallback: download get-pip.py
    try:
        print("Downloading get-pip.py...")
        url = "https://bootstrap.pypa.io/get-pip.py"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmpfile:
            urllib.request.urlretrieve(url, tmpfile.name)
            print("Running get-pip.py...")
            subprocess.check_call([sys.executable, tmpfile.name])
        return
    except Exception as e:
        print(f"Failed to install pip: {e}")
        print("Please install pip manually and re-run this script.")
        sys.exit(1)


def install_packages():
    ensure_pip()
    print("Installing required Python packages...")
    for package in REQUIRED_PACKAGES:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    print("All Python packages installed.")


def install_chrome_windows():
    print("Installing Google Chrome on Windows...")
    import tempfile
    import urllib.request
    chrome_url = "https://dl.google.com/chrome/install/latest/chrome_installer.exe"
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "chrome_installer.exe")
    print(f"Downloading Chrome installer to {installer_path}...")
    urllib.request.urlretrieve(chrome_url, installer_path)
    print("Running Chrome installer...")
    subprocess.run([installer_path, "/silent", "/install"], check=True)
    print("Google Chrome installation complete.")


def install_chrome_linux():
    print("Installing Google Chrome on Linux...")
    distro = platform.linux_distribution()[0].lower() if hasattr(platform, 'linux_distribution') else ''
    if shutil.which("apt"):
        # Debian/Ubuntu
        subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y", "wget"], check=True)
        subprocess.run(["wget", "-O", "/tmp/google-chrome.deb", "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"], check=True)
        subprocess.run(["sudo", "dpkg", "-i", "/tmp/google-chrome.deb"], check=False)
        subprocess.run(["sudo", "apt", "-f", "install", "-y"], check=True)
    elif shutil.which("dnf"):
        # Fedora
        subprocess.run(["sudo", "dnf", "install", "-y", "https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm"], check=True)
    elif shutil.which("yum"):
        # RHEL/CentOS
        subprocess.run(["sudo", "yum", "install", "-y", "https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm"], check=True)
    else:
        print("Unsupported Linux distribution. Please install Google Chrome manually.")
        sys.exit(1)
    print("Google Chrome installation complete.")


def is_python312_installed():
    import shutil
    # Try to find python3.12 in PATH
    python_execs = ["python3.12", "python3_12", "python312", "py -3.12"]
    for exe in python_execs:
        if shutil.which(exe):
            return exe
    # On Windows, check common install locations
    if platform.system() == "Windows":
        possible_paths = [
            r"C:\\Python312\\python.exe",
            os.path.expandvars(r"%LocalAppData%\\Programs\\Python\\Python312\\python.exe"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
    return None


def download_and_install_python_windows():
    import tempfile
    import urllib.request
    print("Downloading Python 3.12 installer for Windows...")
    url = "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "python-3.12.0-amd64.exe")
    urllib.request.urlretrieve(url, installer_path)
    print("Running Python installer silently...")
    # /quiet InstallAllUsers=1 PrependPath=1
    subprocess.run([installer_path, "/quiet", "InstallAllUsers=1", "PrependPath=1"], check=True)
    print("Python 3.12 installation complete. Please restart your terminal if PATH was updated.")


def download_and_install_python_linux():
    import shutil
    import tempfile
    import urllib.request
    import tarfile
    if shutil.which("apt"):  # Ubuntu/Debian
        print("Installing Python 3.12 using apt...")
        subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y", "python3.12", "python3.12-venv", "python3.12-distutils"], check=True)
        return
    elif shutil.which("dnf"):  # Fedora
        print("Installing Python 3.12 using dnf...")
        subprocess.run(["sudo", "dnf", "install", "-y", "python3.12"], check=True)
        return
    elif shutil.which("yum"):  # RHEL/CentOS
        print("Installing Python 3.12 using yum...")
        subprocess.run(["sudo", "yum", "install", "-y", "python3.12"], check=True)
        return
    # Fallback: build from source
    print("Building Python 3.12 from source (this may take a while)...")
    url = "https://www.python.org/ftp/python/3.12.0/Python-3.12.0.tgz"
    temp_dir = tempfile.gettempdir()
    tar_path = os.path.join(temp_dir, "Python-3.12.0.tgz")
    urllib.request.urlretrieve(url, tar_path)
    src_dir = os.path.join(temp_dir, "Python-3.12.0")
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(temp_dir)
    os.chdir(src_dir)
    subprocess.run(["sudo", "apt", "update"], check=False)
    subprocess.run(["sudo", "apt", "install", "-y", "build-essential", "libssl-dev", "zlib1g-dev", "libncurses5-dev", "libncursesw5-dev", "libreadline-dev", "libsqlite3-dev", "libgdbm-dev", "libdb5.3-dev", "libbz2-dev", "libexpat1-dev", "liblzma-dev", "tk-dev", "libffi-dev", "uuid-dev"], check=False)
    subprocess.run(["./configure", "--enable-optimizations"], check=True)
    subprocess.run(["make", "-j4"], check=True)
    subprocess.run(["sudo", "make", "altinstall"], check=True)
    print("Python 3.12 built and installed.")





def in_venv():
    return (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )


def ensure_venv():
    if in_venv():
        print(f"Running inside virtual environment: {sys.prefix}")
        return sys.executable
    if not os.path.exists(VENV_DIR):
        print(f"Creating virtual environment at {VENV_DIR} ...")
        venv.create(VENV_DIR, with_pip=True)
    venv_bin = os.path.join(VENV_DIR, "bin") if platform.system() != "Windows" else os.path.join(VENV_DIR, "Scripts")
    venv_python = os.path.join(venv_bin, "python3") if platform.system() != "Windows" else os.path.join(venv_bin, "python.exe")
    activate_script = os.path.join(venv_bin, "activate")
    if not os.path.exists(activate_script):
        print(f"[ERROR] Virtual environment created but missing activation script: {activate_script}")
        print("This usually means your Python installation is missing the venv module or is incomplete.")
        # Try to auto-fix on Linux with apt-get
        if platform.system() == "Linux" and shutil.which("apt-get"):
            print("Attempting to install python3.12-venv and python3.12 using apt-get...")
            try:
                subprocess.check_call(["sudo", "apt-get", "update"])
                subprocess.check_call(["sudo", "apt-get", "install", "-y", "python3.12-venv", "python3.12"])
                print("Successfully installed venv dependencies. Re-creating virtual environment...")
                shutil.rmtree(VENV_DIR, ignore_errors=True)
                venv.create(VENV_DIR, with_pip=True)
                # Check again for activate script
                if not os.path.exists(activate_script):
                    print(f"[ERROR] Still missing activation script after attempted fix: {activate_script}")
                    sys.exit(1)
                print(f"Re-launching script inside virtual environment: {venv_python}")
                os.execv(venv_python, [venv_python] + sys.argv)
            except Exception as e:
                print(f"[ERROR] Failed to auto-install venv dependencies: {e}")
                print("Please run the following manually and re-run this script:")
                print("  sudo apt-get update && sudo apt-get install python3.12-venv python3.12")
                sys.exit(1)
        elif platform.system() == "Darwin":
            print("Try: brew install python@3.12")
        elif platform.system() == "Windows":
            print("Try repairing your Python installation and ensure 'venv' is included.")
        sys.exit(1)
    print(f"Re-launching script inside virtual environment: {venv_python}")
    os.execv(venv_python, [venv_python] + sys.argv)


# --- CRLF/LF check for Linux ---
def check_line_endings():
    if platform.system() == "Linux":
        with open(__file__, 'rb') as f:
            first_line = f.readline()
            if b'\r' in first_line:
                print("\033[91m[ERROR]\033[0m This script has Windows (CRLF) line endings. Please convert to Unix (LF) line endings:")
                print("Run: dos2unix install_requirements.py OR sed -i 's/\r$//' install_requirements.py")
                sys.exit(1)


def fix_chromedriver_permissions():
    """Find and fix permissions for chromedriver binaries downloaded by webdriver-manager."""
    # Typical webdriver-manager cache location
    home = os.path.expanduser("~")
    chromedriver_glob = os.path.join(home, ".wdm", "drivers", "chromedriver", "linux64", "*", "chromedriver-linux64", "chromedriver")
    chromedrivers = glob.glob(chromedriver_glob)
    fixed = False
    for chromedriver in chromedrivers:
        try:
            st = os.stat(chromedriver)
            # If not executable by user, fix it
            if not (st.st_mode & 0o100):
                os.chmod(chromedriver, st.st_mode | 0o755)
                print(f"[INFO] Set executable permission on: {chromedriver}")
                fixed = True
        except Exception as e:
            print(f"[WARNING] Could not set permissions on {chromedriver}: {e}")
    if not chromedrivers:
        print("[INFO] No chromedriver binaries found to fix permissions.")
    elif not fixed:
        print("[INFO] All found chromedriver binaries already have executable permissions.")


def main():
    check_line_endings()
    #ensure_python312()
    ensure_venv()
    check_python_version()
    install_packages()
    if platform.system() == "Windows":
        install_chrome_windows()
    elif platform.system() == "Linux":
        install_chrome_linux()
    else:
        print("Unsupported OS. Please install Google Chrome manually.")
        sys.exit(1)
    fix_chromedriver_permissions()
    print("All requirements installed successfully.")


if __name__ == "__main__":
    main()

