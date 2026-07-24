import os
import json
from urllib.parse import urlparse
from utils.status import good


CONFIG_FILE = "config.json"
DEFAULT_RHOST = "http://127.0.0.1:3050"
DEFAULT_LHOST = "http://127.0.0.1:3050"
DEFAULT_TOKEN = "IZANAMII"

PACKAGE = "com.example.wirelessdebugtoggle"
ZEROTIER_PACKAGE = "com.zerotier.one"

UI_DUMP_REMOTE = "/sdcard/window_dump.xml"
UI_DUMP_LOCAL = "window_dump.xml"

def config(rhost: str, lhost: str, token: str):
    if rhost is not None:
        save_rhost(rhost)
    if lhost is not None:
        save_lhost(lhost)
    if token is not None:
        save_token(token)

def _load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)


def _normalize_host(value):
    if not value.startswith(("http://", "https://")):
        value = "http://" + value

    value = value.rstrip("/")
    parsed = urlparse(value)

    if parsed.port is None:
        value = f"{parsed.scheme}://{parsed.hostname}:3050"

    return value


# ---- getters ----

def getrhost():
    return _load_config().get("rhost", DEFAULT_RHOST)


def getlhost():
    return _load_config().get("lhost", DEFAULT_LHOST)


def gettoken():
    return _load_config().get("token", DEFAULT_TOKEN)


# ---- setters ----
def save_config(key: str, value):
    data = _load_config()
    if key in data:
        return data[key]
    data[key] = value
    _save_config(data)
    return value

def save_rhost(rhost):
    rhost = _normalize_host(rhost)
    data = _load_config()
    data["rhost"] = rhost
    _save_config(data)
    good(f"rhost set to {rhost}")


def save_lhost(lhost):
    lhost = _normalize_host(lhost)
    data = _load_config()
    data["lhost"] = lhost
    _save_config(data)
    good(f"lhost set to {lhost}")


def save_token(token):
    data = _load_config()
    data["token"] = token
    _save_config(data)
    good("Auth token updated.")