#!/usr/bin/env python3

import sys
import shutil

from utils.status import *
from utils.config import *

from lib.cli import *
from lib.endpoints.inject import inject
from lib.endpoints.control import control_mode
from lib.endpoints.zerotier import zt_join, zt_open, zt_close, zt_status, zt_list, zt_dump
from lib.endpoints.wirelessdebugging import wd
from lib.endpoints.location import loc

# ---------------------------------------------------------------------------
# CLI command registrations
# ---------------------------------------------------------------------------

cli = CLI()


@cli.register("inject", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_inject(result):
    note_runtime(result)
    inject()


@cli.register("wd-open", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_wd_open(result):
    note_runtime(result)
    wd("open")


@cli.register("wd-close", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_wd_close(result):
    note_runtime(result)
    wd("close")


@cli.register("wd-status", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_wd_status(result):
    note_runtime(result)
    wd("status")


@cli.register("loc-open", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_loc_open(result):
    note_runtime(result)
    loc("open")


@cli.register("loc-close", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_loc_close(result):
    note_runtime(result)
    loc("close")


@cli.register("loc-status", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_loc_status(result):
    note_runtime(result)
    loc("status")


@cli.register("zt-join", min_property=0, max_property=None).option("network", str, Appearance.MUST, None, Order.ANY).option("apk", str, Appearance.OPTIONAL, "", Order.ANY).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_zt_join(result):
    note_runtime(result)
    zt_join(result["network"], result["apk"] or None)


@cli.register("zt-open", min_property=0, max_property=None).option("network", str, Appearance.MUST, None, Order.ANY).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_zt_open(result):
    note_runtime(result)
    zt_open(result["network"])


@cli.register("zt-close", min_property=0, max_property=None).option("network", str, Appearance.MUST, None, Order.ANY).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_zt_close(result):
    note_runtime(result)
    zt_close(result["network"])


@cli.register("zt-status", min_property=0, max_property=None).option("network", str, Appearance.MUST, None, Order.ANY).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_zt_status(result):
    note_runtime(result)
    zt_status(result["network"])


@cli.register("zt-list", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_zt_list(result):
    note_runtime(result)
    zt_list()


@cli.register("zt-dump", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_zt_dump(result):
    note_runtime(result)
    zt_dump()


@cli.register("control", min_property=0, max_property=None).flag("--adb", Appearance.OPTIONAL, Order.ANY).callback
def cmd_control(result):
    note_runtime(result)
    control_mode()


@cli.register("set", min_property=0, max_property=None).option("target", str, Appearance.MUST, None, Order.ANY).callback
def cmd_set(result):
    save_target(result["target"])


def usage():
    print(f"""
Proton CLI

Usage:

    python3 app.py inject [--adb] : Injects the APK into the connected device and grants necessary permissions.

    python3 app.py wd-open [--adb] : Opens wireless debugging on the device.
    python3 app.py wd-close [--adb] : Closes wireless debugging on the device.
    python3 app.py wd-status [--adb] : Checks the status of wireless debugging on the device.

    python3 app.py loc-open [--adb] : Opens location services on the device.
    python3 app.py loc-close [--adb] : Closes location services on the device.
    python3 app.py loc-status [--adb] : Checks the status of location services on the device.

    python3 app.py zt-join -network <network_id> [-apk path.apk] [--adb] : Installs ZeroTier if needed, joins a network.
    python3 app.py zt-open -network <network_name> [--adb] : Toggles a specific ZeroTier network ON.
    python3 app.py zt-close -network <network_name> [--adb] : Toggles a specific ZeroTier network OFF.
    python3 app.py zt-status -network <network_name> [--adb] : Checks whether a network is joined/connected.
    python3 app.py zt-list [--adb] : Lists all network names currently shown in the app.
    python3 app.py zt-dump [--adb] : Debug helper — prints the live UI layout of the ZeroTier app.

    python3 app.py control [--adb] : Interactive mode — dumps the current screen, lists every
                                      node by index with its clickable/focusable/checked state,
                                      and lets you drive taps/text/focus by index.

    python3 app.py set -target <target> : Sets the API target host.

Examples:

    python3 app.py inject
    python3 app.py wd-open --adb
    python3 app.py loc-status
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