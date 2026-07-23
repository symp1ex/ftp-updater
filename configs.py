import os
import json

config_data = {
    "ftp": {
        "ftp_server": "ftp.server.com",
        "userdata": {
            "encryption": False,
            "ftp_username": "username",
            "ftp_password": "password"
        }
    },
    "update": {
        "ftp_path": "updater",
        "exe_name": "app.exe",
        "attempt_count": 10,
        "attempt_timeout": 10,
        "signature_check_disable_key": "",
        "http_update": {
            "enabled": False,
            "ftp_mirror_update": False,
            "data connection": {
                "encryption": False,
                "url": "http://server.com/updater/"
            }
        }
    },
    "actions": {
        "at_startup": {
            "enabled": False,
            "file_name": "stop.bat",
            "timeout": 15
        },
        "at_completion": {
            "enabled": False,
            "file_name": "start.bat"
        }
    },
    "logs": {
        "level": "info",
        "path": "..\\logs",
        "clear_days": 14
    }
}

def write_json_file(file_name, config, create=False):
    import logger
    try:
        with open(file_name, "w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=4)

        if create == True:
            logger.updater.warning(f"File '{file_name}' was not found. A new configuration file will be created; restart the application")

        logger.updater.info(f"Data written to '{file_name}'")
        logger.updater.debug(config)
    except Exception:
        logger.updater.error(f"Failed to write data to '{file_name}'.", exc_info=True)
        os._exit(1)

def read_config_file(json_file, create=False):
    try:
        with open(json_file, "r", encoding="utf-8") as file:
            config = json.load(file)
            return config
    except FileNotFoundError:
        if create == True:
            write_json_file(json_file, config_data, True)
            os._exit(1)
    except json.JSONDecodeError:
        if create == True:
            write_json_file(json_file, config_data, True)
            os._exit(1)
