# Flogo Applications Folder

Place all your Flogo application files (.zip) here.

## 📁 Expected Files

- **File Type**: `.zip` (Compressed Archive)
- **Content**: Flogo application packages

## 📝 Example

```
flogo/
├── sampleFlogoApp.zip
├── RestAPIService.zip
├── DataProcessor.zip
└── README.md (this file)
```

## ⚙️ Configuration

After placing your `.zip` files here, configure them in `config.json`:

```json
{
    "app_deployment_config": {
        "enabled": true,
        "app_folder": "apps_to_deploy",
        "flogo_apps": [
            {
                "app_file_name": "sampleFlogoApp.zip",
                "app_name": "SampleFlogoApp",
                "build_name": "flogorest",
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

## 🚀 Notes

- Files are automatically read from `apps_to_deploy/flogo/` folder
- Only `.zip` files should be placed here
- File names must match exactly with `app_file_name` in config.json

