import json
import base64
import os

CONFIG_FILE = "config.json"


def _obfuscate(value: str) -> str:
    if not value:
        return ""
    return base64.b64encode(value.encode()).decode()


def _deobfuscate(value: str) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value.encode()).decode()
    except Exception:
        return value


DEFAULT_CONFIG = {
    "openai_api_key": "",
    "matchmaker_email": "",
    "matchmaker_password": "",
    "business": {
        "company_name": "",
        "website": "",
        "description": "",
        "target_audience": "",
        "value_proposition": "",
        "host_name": "",
    },
    "current_pitch": "",
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        data["openai_api_key"] = _deobfuscate(data.get("openai_api_key", ""))
        data["matchmaker_password"] = _deobfuscate(data.get("matchmaker_password", ""))
        if "business" not in data:
            data["business"] = dict(DEFAULT_CONFIG["business"])
        return data
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    to_save = dict(config)
    to_save["openai_api_key"] = _obfuscate(config.get("openai_api_key", ""))
    to_save["matchmaker_password"] = _obfuscate(config.get("matchmaker_password", ""))
    with open(CONFIG_FILE, "w") as f:
        json.dump(to_save, f, indent=2)
