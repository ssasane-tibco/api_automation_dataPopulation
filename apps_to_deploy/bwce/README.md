# BWCE Applications Folder

Place all your BWCE application files (.ear) here.

## 📁 Expected Files

- **File Type**: `.ear` (Enterprise Archive)
- **Content**: BWCE application packages

## 📝 Example

```
bwce/
├── sampleBWCEApp.ear
├── OrderProcessing.ear
├── CustomerService.ear
└── README.md (this file)
```

## ⚙️ Configuration

After placing your `.ear` files here, configure them in `config.json`:

```json
{
    "app_deployment_config": {
        "enabled": true,
        "app_folder": "apps_to_deploy",
        "bwce_apps": [
            {
                "app_file_name": "sampleBWCEApp.ear",
                "app_name": "SampleBWCEApp",
                "make_public": false,
                "scale_instances": 1,
                "deploy_to_dataplanes": ["Dp-Auto-Test"]
            }
        ]
    }
}
```

## 🚀 Notes

- Files are automatically read from `apps_to_deploy/bwce/` folder
- Only `.ear` files should be placed here
- File names must match exactly with `app_file_name` in config.json

