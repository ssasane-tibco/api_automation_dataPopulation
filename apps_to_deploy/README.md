# Application Files Folder

Place your BWCE (.ear) and Flogo (.zip) application files in their respective subfolders.

## 📁 Folder Structure

```
apps_to_deploy/
├── bwce/                    ← BWCE applications folder
│   ├── sampleBWCEApp.ear
│   ├── myBWCEApp.ear
│   └── anotherBWCEApp.ear
├── flogo/                   ← Flogo applications folder
│   ├── sampleFlogoApp.zip
│   ├── myFlogoApp.zip
│   └── anotherFlogoApp.zip
└── README.md (this file)
```

## 📝 Expected File Types

- **BWCE Applications**: `.ear` files → Place in `bwce/` subfolder
- **Flogo Applications**: `.zip` files → Place in `flogo/` subfolder

## 📂 How to Organize

### 1. Create Subfolders (if not exist):
```bash
mkdir bwce
mkdir flogo
```

### 2. Place Your Application Files:

**BWCE Apps** → `apps_to_deploy/bwce/`
```bash
# Copy your .ear files to bwce folder
cp myapp.ear apps_to_deploy/bwce/
```

**Flogo Apps** → `apps_to_deploy/flogo/`
```bash
# Copy your .zip files to flogo folder
cp myapp.zip apps_to_deploy/flogo/
```

## ⚙️ Configuration

After placing your application files here, update `config.json`:

```json
{
    "app_deployment_config": {
        "enabled": true,
        "app_folder": "apps_to_deploy",
        "bwce_apps": [
            {
                "app_file_name": "sampleBWCEApp.ear",
                "app_name": "SampleBWCEApp",
                ...
            }
        ],
        "flogo_apps": [
            {
                "app_file_name": "sampleFlogoApp.zip",
                "app_name": "SampleFlogoApp",
                ...
            }
        ]
    }
}
```

## 🚀 Deploy

```bash
cd ..
python deploy_apps.py
```

---

**Note:** This folder is for application files only. Configuration is in `config.json`.

