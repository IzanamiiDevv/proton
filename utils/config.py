import os
import json
from urllib.parse import urlparse
from utils.status import good


CONFIG_FILE = "config.json"
DEFAULT_TARGET = "http://127.0.0.1:3050"
DEFAULT_TOKEN = "IZANAMII"

PACKAGE = "com.example.wirelessdebugtoggle"
ZEROTIER_PACKAGE = "com.zerotier.one"

UI_DUMP_REMOTE = "/sdcard/window_dump.xml"
UI_DUMP_LOCAL = "window_dump.xml"

def load_target():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_TARGET

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return data.get("target", DEFAULT_TARGET)
    except Exception:
        return DEFAULT_TARGET


def load_token():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_TOKEN

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return data.get("token", DEFAULT_TOKEN)
    except Exception:
        return DEFAULT_TOKEN


def save_token(token):
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}

    data["token"] = token

    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

    good("Auth token updated.")


def save_target(target):
    if not target.startswith(("http://", "https://")):
        target = "http://" + target

    target = target.rstrip("/")
    parsed = urlparse(target)

    if parsed.port is None:
        target = f"{parsed.scheme}://{parsed.hostname}:3050"

    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}

    data["target"] = target

    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

    good(f"Target set to {target}")