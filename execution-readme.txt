# Execution Guide for TIBCO Platform API Automation
This guide provides basic instructions for setting up and running the automation.

## Setup Prerequisites
1. Clone or copy the project folder to your machine.
2. chmod 777 install_requirements.py
3. Install dependencies using following steps:
    a. sed -i 's/\r$//' install_requirements.py
    b. ./install_requirements.py
4. chmod +x /home/ubuntu/.wdm/drivers/chromedriver/linux64/144.0.7559.96/chromedriver-linux64/chromedriver
5. source .venv/bin/activate ((Recommended) Create and activate a Python virtual environment)


## Configuration
- Edit `config.json` to set up your environment, credentials, and deployment options.
- Key fields:
  - `admin_host`, `idp_host`: URLs for admin and IDP endpoints
  - `credentials`: Admin username and password
  - `invite_user_email`, `new_user_details`: Details for the user to be invited
  - `dataplane_config`: Dataplane registration settings
    - `dpCount`: Set to the number of dataplanes to register (for multiple dataplanes)
  - `activation_server_config`: Activation server details
  - `app_deployment_config`: Application deployment options
    - `bwce_apps`, `flogo_apps`: List of apps to deploy

## Running Automation
- To execute the full workflow, run:
  python main.py

  This will perform user invitation, registration, dataplane setup, capability provisioning, and application deployment.

  > **Note:** Always use new values for `target_prefix` and `invite_user_email` in `config.json` before running main.py.

## Deploying Applications Only
- To deploy applications (BWCE/Flogo) without full setup, run:
  python deploy_apps_only.py

  This script deploys apps as defined in `config.json` under `app_deployment_config`.

## Notes
- For multiple dataplanes, set `dpCount` in `dataplane_config` and provide corresponding names/namespaces.
- Ensure all endpoints and credentials are valid and accessible.
