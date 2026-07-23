#!/usr/bin/env python3

import sys
import shutil

from utils.status import *
from utils.config import *

from lib.cli import *
from lib.endpoints.inject import inject
from lib.endpoints.control import control_mode
from lib.endpoints.zerotier import zerotier
from lib.endpoints.wirelessdebugging import wd
from lib.endpoints.location import loc

cli = CLI()

@cli.register("inject", min_property=1, max_property=1).locked([flag("--payload"), flag("--shizuku")], appearance=Appearance.MUST, order=Order.LOCK).callback
def cmd_inject(result):
    apk_name = "payload" if "--payload" in result and result["--payload"] else "shizuku" if "--shizuku" in result and result["--shizuku"] else None
    inject(apk_name)

@cli.register("wd", min_property=1, max_property=1).locked([flag("open"), flag("close"), flag("status")], appearance=Appearance.MUST, order=Order.LOCK).callback
def cmd_wd(result):
    if "open" in result and result["open"]: return wd("open")
    if "close" in result and result["close"]: return wd("close")
    if "status" in result and result["status"]: return wd("status")


@cli.register("location", min_property=1, max_property=1).locked([flag("open"), flag("close"), flag("status")], appearance=Appearance.MUST, order=Order.LOCK).callback
def cmd_location(result):
    if "open" in result and result["open"]: return loc("open")
    if "close" in result and result["close"]: return loc("close")
    if "status" in result and result["status"]: return loc("status")

@cli.register("zerotier", min_property=2, max_property=None).locked([flag("join"), flag("open"), flag("close"), flag("status"), flag("list"), flag("dump")], Appearance.MUST, Order.LOCK).locked([flag("--adb"), flag("--shell")], Appearance.MUST, Order.ANY).option("network", str, Appearance.MUST, None, Order.ANY).callback
def cmd_zerotier(result: dict):
    commands: list[str] = ["join", "open", "close", "status", "list", "dump"]
    command: str = next(commands[i] for i in range(len(commands)) if commands[i] in result and result[commands[i]]  and not result[commands[i - 1]] and not result[commands[i - 2]] and not result[commands[i - 3]])
    action: str = "adb" if result["--adb"] and not result["--shell"] else "shell" if result["--shell"] and not result["--adb"] else None
    network: str = result["network"]
    zerotier(command, action, network)
    return None

@cli.register("control", min_property=2, max_property=2).locked([flag("--web"), flag("--cli")], appearance=Appearance.MUST, order=Order.ANY).locked([flag("--adb"), flag("--shell")], appearance=Appearance.MUST, order=Order.ANY).callback
def cmd_control(result):
    mode = "web" if result["--web"] and not result["--cli"] else "cli" if result["--cli"] and not result["--web"] else None
    action = "adb" if result["--adb"] and not result["--shell"] else "shell" if result["--shell"] and not result["--adb"] else None
    print(mode, action)


@cli.register("config", min_property=0, max_property=None).option("rhost", str, Appearance.OPTIONAL, "127.0.0.1:3090", Order.ANY).option("lhost", str, Appearance.OPTIONAL, "127.0.0.1:3050", Order.ANY).callback
def cmd_config(result):
    print(f"rhost: {result["rhost"]}\nlhost: {result["lhost"]}")
    return None


def usage():
    print(f"""
Proton CLI

Usage:

    python3 app.py inject [--adb] : Injects the APK into the connected device and grants necessary permissions.

    python3 app.py location open : Opens location services on the device.
    python3 app.py location close : Closes location services on the device.
    python3 app.py location status : Checks the status of location services on the device.

    python3 app.py zt-join -network <network_id> [-apk path.apk] [--adb] : Installs ZeroTier if needed, joins a network.
    python3 app.py zt-open -network <network_name> [--adb] : Toggles a specific ZeroTier network ON.
    python3 app.py zt-close -network <network_name> [--adb] : Toggles a specific ZeroTier network OFF.
    python3 app.py zt-status -network <network_name> [--adb] : Checks whether a network is joined/connected.
    python3 app.py zt-list [--adb] : Lists all network names currently shown in the app.
    python3 app.py zt-dump [--adb] : Debug helper — prints the live UI layout of the ZeroTier app.

    python3 app.py control [--web or --cli] [--adb or --shell] : Interactive mode — dumps the current screen, lists every
                                      node by index with its clickable/focusable/checked state,
                                      and lets you drive taps/text/focus by index.

    python3 app.py set -target <target> : Sets the API target host.

Examples:

    python3 app.py inject
    python3 app.py wd open
    python3 app.py location status
    python3 app.py zt-join -network 8056c2e21c000001
    python3 app.py zt-open -network "My Network"
    python3 app.py zt-close -network "My Network"
    python3 app.py zt-status -network "My Network"
    python3 app.py zt-list
    python3 app.py control
    python3 app.py set -target 127.0.0.1:3050
""")


def main():
    if shutil.which("adb") is None:
        bad("adb not found in PATH")
        sys.exit(1)

    if len(sys.argv) < 2:
        usage()
        sys.exit(0)

    try:
        cli.run()
    except Exception as e:
        bad(f"Error: {e}")
        sys.exit(1)
        usage()


if __name__ == "__main__":
    main()