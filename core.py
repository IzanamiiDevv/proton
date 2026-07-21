#!/usr/bin/env python3

import os
import sys
import json
import shutil
import subprocess

try:
    import requests
except ImportError:
    print("[!] requests module not installed")
    print("    pip install requests")
    sys.exit(1)

PACKAGE = "com.example.wirelessdebugtoggle"
API = "http://127.0.0.1:3050"


# ----------------------------------------
# Colors
# ----------------------------------------

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


# ----------------------------------------
# Helpers
# ----------------------------------------

def info(msg):
    print(f"{BLUE}[*]{RESET} {msg}")


def good(msg):
    print(f"{GREEN}[+]{RESET} {msg}")


def bad(msg):
    print(f"{RED}[-]{RESET} {msg}")


def adb(cmd):
    command = ["adb"] + cmd

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if result.returncode != 0:
        bad(" ".join(command))
        print(result.stdout.strip())
        sys.exit(1)

    return result.stdout.strip()


def request(endpoint):
    try:
        r = requests.get(API + endpoint, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        bad(str(e))
        sys.exit(1)


# ----------------------------------------
# Inject APK
# ----------------------------------------

def inject():

    apk = os.path.join("dist", "app.apk")

    if not os.path.exists(apk):
        bad(f"APK not found: {apk}")
        return

    info("Installing APK...")
    adb(["install", "-r", apk])

    info("Granting permissions...")

    permissions = [
        "android.permission.WRITE_SECURE_SETTINGS",
        "android.permission.POST_NOTIFICATIONS",
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
    ]

    for perm in permissions:
        adb(["shell", "pm", "grant", PACKAGE, perm])

    info("Whitelisting battery optimization...")
    adb([
        "shell",
        "dumpsys",
        "deviceidle",
        "whitelist",
        "+" + PACKAGE
    ])

    info("Allowing background execution...")
    adb([
        "shell",
        "cmd",
        "appops",
        "set",
        PACKAGE,
        "RUN_IN_BACKGROUND",
        "allow"
    ])

    adb([
        "shell",
        "cmd",
        "appops",
        "set",
        PACKAGE,
        "RUN_ANY_IN_BACKGROUND",
        "allow"
    ])

    info("Launching application...")

    adb([
        "shell",
        "monkey",
        "-p",
        PACKAGE,
        "-c",
        "android.intent.category.LAUNCHER",
        "1"
    ])

    adb([
        "shell",
        "input",
        "keyevent",
        "KEYCODE_HOME"
    ])

    good("Injection completed.")


# ----------------------------------------
# Wireless Debugging
# ----------------------------------------

def wd(action):

    if action == "open":
        print(json.dumps(request("/open"), indent=4))

    elif action == "close":
        print(json.dumps(request("/close"), indent=4))

    elif action == "status":
        data = request("/status")

        if data["enabled"]:
            good("Wireless Debugging: ENABLED")
        else:
            bad("Wireless Debugging: DISABLED")

    else:
        usage()


# ----------------------------------------
# Location
# ----------------------------------------

def loc(action):

    if action == "open":
        print(json.dumps(request("/loc-open"), indent=4))

    elif action == "close":
        print(json.dumps(request("/loc-close"), indent=4))

    elif action == "status":

        data = request("/loc-status")

        print(json.dumps(data, indent=4))

    else:
        usage()


# ----------------------------------------
# Usage
# ----------------------------------------

def usage():

    print(f"""
Wireless Debug Toggle CLI

Usage:

    python3 core.py inject app.apk

    python3 core.py wd open
    python3 core.py wd close
    python3 core.py wd status

    python3 core.py loc open
    python3 core.py loc close
    python3 core.py loc status

Examples:

    python3 core.py inject app.apk
    python3 core.py wd open
    python3 core.py loc status
""")

    sys.exit(0)


# ----------------------------------------
# Main
# ----------------------------------------

def main():

    if shutil.which("adb") is None:
        bad("adb not found in PATH")
        sys.exit(1)

    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1]

    if cmd == "inject":

        if len(sys.argv) != 3:
            usage()

        inject(sys.argv[2])

    elif cmd == "wd":

        if len(sys.argv) != 3:
            usage()

        wd(sys.argv[2])

    elif cmd == "loc":

        if len(sys.argv) != 3:
            usage()

        loc(sys.argv[2])

    else:
        usage()


if __name__ == "__main__":
    main()