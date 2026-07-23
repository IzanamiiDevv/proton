# ---------------------------------------------------------------------------
# ZeroTier automation
# ---------------------------------------------------------------------------
import sys
import os
import time
from string import hexdigits

from utils.status import info, good, bad, warn
from utils.uiautomator import dump_ui, tap_node, input_text, wait_for_focus, press_home, press_back, find_node, find_switch_near, print_ui, is_installed, launch_app
from utils.config import ZEROTIER_PACKAGE

from lib.executor.adb import adb


def zerotier(command: str, action: str, network: str):
    if command == "join" : return zt_join_adb(network) if action == "adb" else None if action == "shell" else None
    if command == "open" : return zt_open_adb(network) if action == "adb" else None if action == "shell" else None
    if command == "close" : return zt_close_adb(network) if action == "adb" else None if action == "shell" else None
    if command == "status" : return zt_status_adb(network) if action == "adb" else None if action == "shell" else None
    if command == "list" : return zt_list_adb() if action == "adb" else None if action == "shell" else None
    if command == "dump" : return zt_dump_adb() if action == "adb" else None if action == "shell" else None

def zt_require_installed():
    if not is_installed(ZEROTIER_PACKAGE):
        bad("ZeroTier is not installed on the device.")
        sys.exit(1)


def zt_join_adb(network_id: str):
    if not network_id or not all(c in hexdigits for c in network_id):
        return bad("network id is not base16")
    
    if not is_installed(ZEROTIER_PACKAGE):
        if not apk_path:
            apk_path = os.path.join("dist", "zerotier.apk")

        if not os.path.exists(apk_path):
            bad(f"ZeroTier APK not found: {apk_path}")
            info("Pass it explicitly with -apk <path> or place it at dist/zerotier.apk")
            return

        info("Installing ZeroTier...")
        adb(["install", "-r", apk_path])
    else:
        info("ZeroTier already installed.")

    info("Launching ZeroTier...")
    launch_app(ZEROTIER_PACKAGE)

    info("Reading screen layout...")
    root = dump_ui(delay=1.5)

    add_network_node = find_node(root, text="ADD NETWORK", exact=False)
    if add_network_node is None:
        bad('Could not find "ADD NETWORK" button. Run "zt-dump" to inspect the live layout.')
        return

    tap_node(add_network_node)

    info("Reading network id dialog...")
    root = dump_ui(delay=1.0)

    field_node = find_node(root, resource_id="add_network_edit_text", class_name="EditText")
    if field_node is None:
        # fall back to hint-text matching in case the resource-id ever changes
        field_node = find_node(root, text="16 hex characters", class_name="EditText", exact=False)
    if field_node is None:
        bad('Could not find the network id input field. Run "zt-dump" to inspect the live layout.')
        return

    tap_node(field_node)

    info("Waiting for network id field to focus...")
    focused_node = wait_for_focus(resource_id="add_network_edit_text", class_name="EditText")
    if focused_node is None:
        bad("Network id field never gained focus. Run \"zt-dump\" to inspect the live layout.")
        return

    input_text(network_id)

    info("Dismissing keyboard...")
    press_back()
    time.sleep(0.5)

    root = dump_ui(delay=0.5)
    add_button = find_node(root, text="Add", exclude_text="network")
    if add_button is None:
        bad('Could not find the "Add" confirmation button. Run "zt-dump" to inspect the live layout.')
        return

    tap_node(add_button)

    press_home()
    good(f"Joined ZeroTier network {network_id}")


def zt_open_adb(network_name: str):
    zt_require_installed()

    launch_app(ZEROTIER_PACKAGE)
    root = dump_ui(delay=1.5)

    network_node = find_node(root, text=network_name, exact=False)
    if network_node is None:
        bad(f'Network "{network_name}" not found on this device.')
        press_home()
        return

    switch = find_switch_near(root, network_name)
    if switch is None:
        bad("Could not find that network's toggle switch. Run \"zt-dump\" to inspect the live layout.")
        return

    checked = switch.attrib.get("checked", "false") == "true"
    if checked:
        good(f'Network "{network_name}" already ON.')
    else:
        tap_node(switch)
        good(f'Network "{network_name}" turned ON.')

    press_home()


def zt_close_adb(network_name: str):
    zt_require_installed()

    launch_app(ZEROTIER_PACKAGE)
    root = dump_ui(delay=1.5)

    network_node = find_node(root, text=network_name, exact=False)
    if network_node is None:
        bad(f'Network "{network_name}" not found on this device.')
        press_home()
        return

    switch = find_switch_near(root, network_name)
    if switch is None:
        bad("Could not find that network's toggle switch. Run \"zt-dump\" to inspect the live layout.")
        return

    checked = switch.attrib.get("checked", "false") == "true"
    if checked:
        tap_node(switch)
        good(f'Network "{network_name}" turned OFF.')
    else:
        good(f'Network "{network_name}" already OFF.')

    press_home()


def zt_status_adb(network_name: str):
    zt_require_installed()

    launch_app(ZEROTIER_PACKAGE)
    root = dump_ui(delay=1.5)

    node = find_node(root, text=network_name, exact=False)
    if node is None:
        bad(f'Network "{network_name}" not found on this device.')
        press_home()
        return

    switch = find_switch_near(root, network_name)
    state = "UNKNOWN"
    if switch is not None:
        state = "ON" if switch.attrib.get("checked", "false") == "true" else "OFF"

    good(f'Network "{network_name}" found. State: {state}')
    press_home()


def zt_list_adb():
    zt_require_installed()

    launch_app(ZEROTIER_PACKAGE)
    root = dump_ui(delay=1.5)

    texts = [
        node.attrib.get("text", "").strip()
        for node in root.iter("node")
        if "textview" in node.attrib.get("class", "").lower() and node.attrib.get("text", "").strip()
    ]

    # Each network card repeats a "Network ID" label followed by its value,
    # and a "Network Name" label followed by its value (plus other footer
    # chrome we don't care about here — node address, status, app version,
    # etc). A "Network ID" label marks the start of a new card.
    entries = []
    current = {}
    i = 0

    while i < len(texts):
        label = texts[i].lower()

        if label == "network id":
            if current:
                entries.append(current)
            current = {}
            if i + 1 < len(texts):
                current["id"] = texts[i + 1]
            i += 2
            continue

        if label == "network name":
            if i + 1 < len(texts):
                current["name"] = texts[i + 1]
            i += 2
            continue

        i += 1

    if current:
        entries.append(current)

    if not entries:
        warn('No networks found. Run "zt-dump" to inspect the live layout.')
        press_home()
        return

    good(f"Found {len(entries)} network(s):")
    for entry in entries:
        name = entry.get("name", "?")
        network_id = entry.get("id", "?")
        print(f"Network Name: {name} : Network ID: {network_id}")

    press_home()


def zt_dump_adb():
    """Debug command: launch ZeroTier, dump the current screen, print raw nodes."""
    zt_require_installed()
    launch_app(ZEROTIER_PACKAGE)
    root = dump_ui(delay=1.5)
    print_ui(root)

def zt_join_shell(network_id: str):
    if not network_id or not all(c in hexdigits for c in network_id):
            return bad("network id is not base16")

    
    return None

def zt_open_shell(network_name: str):
    return None

def zt_close_shell(network_name: str):
    return None

def zt_status_shell(network_name: str):
    return None

def zt_list_shell():
    return None

def zt_demp_shell():
    return None