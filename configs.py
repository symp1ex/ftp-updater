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
        "enabled": True,
        "ftp_path": "updater",
        "exe_name": "name.exe",
        "attempt_count": 20,
        "attempt_timeout": 20,
        "signature_check_disable_key": ""
    },
    "send_data": {
        "enabled": False,
        "local_path": "..\\date",
        "attempt_count": 20,
        "attempt_timeout": 20
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

def write_json_file(file_name, config):
    import logger
    try:
        with open(file_name, "w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=4)
        logger.updater.info(f"Данные записаны в '{file_name}'")
        logger.updater.debug(config)
    except Exception:
        logger.updater.error(f"Не удалось записать данные в '{file_name}'.")
        pass

def read_config_file(json_file, create=False):
    try:
        with open(json_file, "r", encoding="utf-8") as file:
            config = json.load(file)
            return config
    except FileNotFoundError:
        if create == True:
            write_json_file(json_file, config_data)
    except json.JSONDecodeError:
        if create == True:
            write_json_file(json_file, config_data)