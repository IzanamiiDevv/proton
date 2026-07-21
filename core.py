#!/usr/bin/env python3

import os
import re
import sys
import json
import time
import shutil
import subprocess
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

CONFIG_FILE = "config.json"
DEFAULT_TARGET = "http://127.0.0.1:3050"

try:
    import requests
except ImportError:
    print("[!] requests module not installed")
    print("    pip install requests")
    sys.exit(1)

PACKAGE = "com.example.wirelessdebugtoggle"
ZEROTIER_PACKAGE = "com.zerotier.one"

UI_DUMP_REMOTE = "/sdcard/window_dump.xml"
UI_DUMP_LOCAL = "window_dump.xml"


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def info(msg):
    print(f"{BLUE}[*]{RESET} {msg}")


def good(msg):
    print(f"{GREEN}[+]{RESET} {msg}")


def bad(msg):
    print(f"{RED}[-]{RESET} {msg}")


def warn(msg):
    print(f"{YELLOW}[!]{RESET} {msg}")


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

    api = load_target()

    try:
        r = requests.get(api + endpoint, timeout=5)
        r.raise_for_status()
        return r.json()

    except Exception as e:
        bad(str(e))
        sys.exit(1)


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


# ---------------------------------------------------------------------------
# UIAutomator helpers (shared by all UI-driven automation, e.g. ZeroTier)
# ---------------------------------------------------------------------------

def is_installed(package):
    out = adb(["shell", "pm", "list", "packages", package])
    return package in out


def launch_app(package):
    adb([
        "shell",
        "monkey",
        "-p",
        package,
        "-c",
        "android.intent.category.LAUNCHER",
        "1"
    ])


def press_home():
    adb(["shell", "input", "keyevent", "KEYCODE_HOME"])


def press_back():
    adb(["shell", "input", "keyevent", "KEYCODE_BACK"])


def dump_ui(delay=1.0):
    """
    Dump the current screen layout via uiautomator, pull it locally, and
    parse it into an ElementTree root. `delay` gives the UI time to settle
    before we dump (animations, screen transitions, etc).
    """
    time.sleep(delay)
    adb(["shell", "uiautomator", "dump", UI_DUMP_REMOTE])

    if os.path.exists(UI_DUMP_LOCAL):
        os.remove(UI_DUMP_LOCAL)

    adb(["pull", UI_DUMP_REMOTE, UI_DUMP_LOCAL])
    tree = ET.parse(UI_DUMP_LOCAL)
    return tree.getroot()


def print_ui(root):
    """Debug helper: dump every visible node to stdout (text/resource-id/bounds)."""
    for node in root.iter("node"):
        text = node.attrib.get("text", "")
        rid = node.attrib.get("resource-id", "")
        clazz = node.attrib.get("class", "")
        bounds = node.attrib.get("bounds", "")
        if text or rid:
            print(f"Text: {text}")
            print(f"Resource ID: {rid}")
            print(f"Class: {clazz}")
            print(f"Bounds: {bounds}")
            print("-" * 40)


def center(bounds):
    nums = list(map(int, re.findall(r"\d+", bounds)))
    x = (nums[0] + nums[2]) // 2
    y = (nums[1] + nums[3]) // 2
    return x, y


def tap_bounds(bounds):
    x, y = center(bounds)
    adb(["shell", "input", "tap", str(x), str(y)])


def tap_node(node):
    bounds = node.attrib.get("bounds")
    if not bounds:
        raise ValueError("Node has no bounds to tap")
    tap_bounds(bounds)


def input_text(text):
    # `adb shell input text` treats raw spaces as separate key events / breaks
    # on some devices, so escape them the way adb expects.
    escaped = text.replace(" ", "%s")
    adb(["shell", "input", "text", escaped])


def find_node(root, text=None, resource_id=None, class_name=None, exact=True, contains_ok=True, exclude_text=None):
    """
    Find the first node matching text / resource-id / class-name.
    Exact text match first; if nothing hits and contains_ok, retry with a
    case-insensitive substring match (UI label casing varies by app version).
    exclude_text, if given, rules out any node whose text also contains that
    substring — useful when a broad match (e.g. "Add") would otherwise catch
    an unrelated lookalike (e.g. "ADD NETWORK").
    """

    def matches(node):
        node_text = node.attrib.get("text", "")
        if exclude_text is not None and exclude_text.lower() in node_text.lower():
            return False
        if text is not None:
            if exact:
                if node_text.lower() != text.lower():
                    return False
            else:
                if text.lower() not in node_text.lower():
                    return False
        if resource_id is not None:
            if resource_id.lower() not in node.attrib.get("resource-id", "").lower():
                return False
        if class_name is not None:
            if class_name.lower() not in node.attrib.get("class", "").lower():
                return False
        return True

    for node in root.iter("node"):
        if matches(node):
            return node

    if text is not None and exact and contains_ok:
        return find_node(root, text=text, resource_id=resource_id,
                          class_name=class_name, exact=False, contains_ok=False,
                          exclude_text=exclude_text)

    return None


def wait_for_focus(resource_id=None, class_name=None, text=None, retries=6, delay=0.4):
    """
    Tap-and-verify loop for a target node: re-dumps the UI and checks the
    node's `focused` attribute, re-tapping if it isn't focused yet. This
    closes the classic ADB race where `input text` fires while the
    EditText is still mid-focus-animation and eats the first keystrokes.
    Returns the focused node, or None if it never focused after `retries`
    attempts.
    """
    for _ in range(retries):
        root = dump_ui(delay=delay)
        node = find_node(root, resource_id=resource_id, class_name=class_name, text=text)
        if node is None:
            return None
        if node.attrib.get("focused", "false") == "true":
            return node
        tap_node(node)

    root = dump_ui(delay=delay)
    node = find_node(root, resource_id=resource_id, class_name=class_name, text=text)
    if node is not None and node.attrib.get("focused", "false") == "true":
        return node

    return None


def find_switch(root):
    """Find the first toggle/switch-like node on screen (single-network fallback)."""
    for node in root.iter("node"):
        clazz = node.attrib.get("class", "").lower()
        if "switch" in clazz or "togglebutton" in clazz:
            return node
    return None


def find_switch_near(root, network_name):
    """
    Find the toggle/switch belonging to a specific network's row.
    Heuristic: locate the node whose text matches network_name, then look
    for the nearest Switch/ToggleButton node in document order — first
    scanning forward (switch usually rendered after or as a sibling of the
    label), then backward if nothing turns up.
    """
    nodes = list(root.iter("node"))
    label_index = None

    for i, node in enumerate(nodes):
        if network_name.lower() in node.attrib.get("text", "").lower():
            label_index = i
            break

    if label_index is None:
        return None

    def is_switch(node):
        clazz = node.attrib.get("class", "").lower()
        return "switch" in clazz or "togglebutton" in clazz

    for node in nodes[label_index:]:
        if is_switch(node):
            return node

    for node in reversed(nodes[:label_index]):
        if is_switch(node):
            return node

    return None


# ---------------------------------------------------------------------------
# ZeroTier automation
# ---------------------------------------------------------------------------

def zt_require_installed():
    if not is_installed(ZEROTIER_PACKAGE):
        bad("ZeroTier is not installed on the device.")
        info('Run: python3 core.py zt join <network_id> --apk <path-to-zerotier.apk>')
        sys.exit(1)


def zt_join(network_id, apk_path=None):

    if not is_installed(ZEROTIER_PACKAGE):
        if not apk_path:
            apk_path = os.path.join("dist", "zerotier.apk")

        if not os.path.exists(apk_path):
            bad(f"ZeroTier APK not found: {apk_path}")
            info("Pass it explicitly with --apk <path> or place it at dist/zerotier.apk")
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
        bad('Could not find "ADD NETWORK" button. Run "zt dump" to inspect the live layout.')
        return

    tap_node(add_network_node)

    info("Reading network id dialog...")
    root = dump_ui(delay=1.0)

    field_node = find_node(root, resource_id="add_network_edit_text", class_name="EditText")
    if field_node is None:
        # fall back to hint-text matching in case the resource-id ever changes
        field_node = find_node(root, text="16 hex characters", class_name="EditText", exact=False)
    if field_node is None:
        bad('Could not find the network id input field. Run "zt dump" to inspect the live layout.')
        return

    tap_node(field_node)

    info("Waiting for network id field to focus...")
    focused_node = wait_for_focus(resource_id="add_network_edit_text", class_name="EditText")
    if focused_node is None:
        bad("Network id field never gained focus. Run \"zt dump\" to inspect the live layout.")
        return

    input_text(network_id)

    info("Dismissing keyboard...")
    press_back()
    time.sleep(0.5)

    root = dump_ui(delay=0.5)
    add_button = find_node(root, text="Add", exclude_text="network")
    if add_button is None:
        bad('Could not find the "Add" confirmation button. Run "zt dump" to inspect the live layout.')
        return

    tap_node(add_button)

    press_home()
    good(f"Joined ZeroTier network {network_id}")


def zt_open(network_name):
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
        bad("Could not find that network's toggle switch. Run \"zt dump\" to inspect the live layout.")
        return

    checked = switch.attrib.get("checked", "false") == "true"
    if checked:
        good(f'Network "{network_name}" already ON.')
    else:
        tap_node(switch)
        good(f'Network "{network_name}" turned ON.')

    press_home()


def zt_close(network_name):
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
        bad("Could not find that network's toggle switch. Run \"zt dump\" to inspect the live layout.")
        return

    checked = switch.attrib.get("checked", "false") == "true"
    if checked:
        tap_node(switch)
        good(f'Network "{network_name}" turned OFF.')
    else:
        good(f'Network "{network_name}" already OFF.')

    press_home()


def zt_status(network_name):
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


def zt_list():
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
        warn('No networks found. Run "zt dump" to inspect the live layout.')
        press_home()
        return

    good(f"Found {len(entries)} network(s):")
    for entry in entries:
        name = entry.get("name", "?")
        network_id = entry.get("id", "?")
        print(f"Network Name: {name} : Network ID: {network_id}")

    press_home()


def zt_dump():
    """Debug command: launch ZeroTier, dump the current screen, print raw nodes."""
    zt_require_installed()
    launch_app(ZEROTIER_PACKAGE)
    root = dump_ui(delay=1.5)
    print_ui(root)


# ---------------------------------------------------------------------------
# Interactive control mode — drive the device node-by-node off a live dump
# ---------------------------------------------------------------------------

def describe_node_flags(attrib):
    flags = []

    if attrib.get("clickable") == "true":
        flags.append("clickable")
    if attrib.get("long-clickable") == "true":
        flags.append("long-clickable")
    if attrib.get("checkable") == "true":
        state = "checked" if attrib.get("checked") == "true" else "unchecked"
        flags.append(f"checkable:{state}")
    if attrib.get("focusable") == "true":
        state = "focused" if attrib.get("focused") == "true" else "unfocused"
        flags.append(f"focusable:{state}")
    if attrib.get("scrollable") == "true":
        flags.append("scrollable")
    if attrib.get("enabled") == "false":
        flags.append("disabled")

    return ", ".join(flags) if flags else "static"


def print_nodes(nodes):
    print()
    for i, node in enumerate(nodes):
        attrib = node.attrib
        text = attrib.get("text", "")
        rid = attrib.get("resource-id", "")
        clazz = attrib.get("class", "")
        bounds = attrib.get("bounds", "")

        label = text or rid or clazz or "(no text/id)"

        print(f"[{i}] {label}")
        print(f"     id={rid}  class={clazz}")
        print(f"     bounds={bounds}")
        print(f"     flags: {describe_node_flags(attrib)}")
    print()


def print_control_help():
    print(f"""
Control mode commands:

    list | ls                 Re-print the current node list
    refresh | r                Re-dump the screen and re-print the node list
    node=<i> --click            Tap node <i>
    node=<i> --focus            Tap node <i>, then wait until it reports focused
    node=<i> --text <value>     Type <value> (tap/--focus the node first so it actually has focus)
    node=<i> --info             Print all raw attributes for node <i>
    back                       Press the BACK key
    home                       Press the HOME key
    help | h | ?                Show this list
    exit | quit | q             Leave control mode
""")


def control_mode():
    info('Entering control mode. Type "help" for commands, "exit" to quit.')

    nodes = []

    def refresh():
        nonlocal nodes
        info("Reading window layout...")
        root = dump_ui(delay=0.5)
        nodes = list(root.iter("node"))
        print_nodes(nodes)

    refresh()

    while True:
        try:
            raw = input(f"{BLUE}control>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not raw:
            continue

        if raw in ("exit", "quit", "q"):
            break

        if raw in ("help", "h", "?"):
            print_control_help()
            continue

        if raw in ("list", "ls"):
            print_nodes(nodes)
            continue

        if raw in ("refresh", "r"):
            refresh()
            continue

        if raw == "home":
            press_home()
            continue

        if raw == "back":
            press_back()
            continue

        parts = raw.split(None, 2)
        match = re.match(r"node=(\d+)$", parts[0]) if parts else None

        if not match:
            warn('Unrecognized command. Type "help" for the command list.')
            continue

        idx = int(match.group(1))
        if idx < 0 or idx >= len(nodes):
            bad(f'No node with index {idx}. Type "list" to see valid indices.')
            continue

        node = nodes[idx]
        flag = parts[1] if len(parts) > 1 else None

        if flag == "--click":
            if node.attrib.get("clickable") != "true":
                warn(f"Node {idx} is not marked clickable, tapping anyway...")
            tap_node(node)
            good(f"Tapped node {idx}.")

        elif flag == "--focus":
            resource_id = node.attrib.get("resource-id") or None
            class_name = node.attrib.get("class") or None
            tap_node(node)
            focused_node = wait_for_focus(resource_id=resource_id, class_name=class_name)
            if focused_node is not None:
                good(f"Node {idx} is now focused.")
            else:
                bad(f"Node {idx} never gained focus.")

        elif flag == "--text":
            if len(parts) < 3:
                warn("Usage: node=<i> --text <value>")
                continue
            value = parts[2].strip().strip('"')
            input_text(value)
            good(f'Typed "{value}" (tap/--focus the node first, or this may drop characters).')

        elif flag == "--info":
            print(json.dumps(node.attrib, indent=4))

        else:
            warn('Unknown flag. Type "help" for the command list.')


def usage():

    print(f"""
Proton CLI

Usage:

    [adb required] python3 core.py inject app.apk : Injects the APK into the connected device and grants necessary permissions.

    python3 core.py wd open : Opens wireless debugging on the device.
    python3 core.py wd close : Closes wireless debugging on the device.
    python3 core.py wd status : Checks the status of wireless debugging on the device.

    [adb required] python3 core.py loc open : Opens location services on the device.
    [adb required] python3 core.py loc close : Closes location services on the device.
    [adb required] python3 core.py loc status : Checks the status of location services on the device.

    [adb required] python3 core.py zt join <network_id> [--apk path.apk] : Installs ZeroTier if needed, joins a network.
    [adb required] python3 core.py zt open <network_name> : Toggles a specific ZeroTier network ON.
    [adb required] python3 core.py zt close <network_name> : Toggles a specific ZeroTier network OFF.
    [adb required] python3 core.py zt status <network_name> : Checks whether a network is joined/connected.
    [adb required] python3 core.py zt list : Lists all network names currently shown in the app.
    [adb required] python3 core.py zt dump : Debug helper — prints the live UI layout of the ZeroTier app.

    [adb required] python3 core.py control : Interactive mode — dumps the current screen, lists every
                              node by index with its clickable/focusable/checked state,
                              and lets you drive taps/text/focus by index.

Examples:

    python3 core.py inject app.apk
    python3 core.py wd open
    python3 core.py loc status
    python3 core.py zt join 8056c2e21c000001
    python3 core.py zt open "My Network"
    python3 core.py zt close "My Network"
    python3 core.py zt status "My Network"
    python3 core.py zt list
    python3 core.py control
""")

    sys.exit(0)


def main():
    if shutil.which("adb") is None:
        bad("adb not found in PATH")
        sys.exit(1)

    if len(sys.argv) < 2:
        usage()
    cmd = sys.argv[1]

    if cmd == "inject":
        if len(sys.argv) != 2:
            usage()
        inject()

    elif cmd == "wd":
        if len(sys.argv) != 3:
            usage()
        wd(sys.argv[2])

    elif cmd == "loc":
        if len(sys.argv) != 3:
            usage()
        loc(sys.argv[2])

    elif cmd == "zt":
        if len(sys.argv) < 3:
            usage()
        sub = sys.argv[2]

        if sub == "join":
            if len(sys.argv) < 4:
                usage()
            network_id = sys.argv[3]

            apk_path = None
            if "--apk" in sys.argv:
                idx = sys.argv.index("--apk")
                if idx + 1 < len(sys.argv):
                    apk_path = sys.argv[idx + 1]
                else:
                    usage()

            zt_join(network_id, apk_path)

        elif sub == "open":
            if len(sys.argv) != 4:
                usage()
            zt_open(sys.argv[3])

        elif sub == "close":
            if len(sys.argv) != 4:
                usage()
            zt_close(sys.argv[3])

        elif sub == "status":
            if len(sys.argv) != 4:
                usage()
            zt_status(sys.argv[3])

        elif sub == "list":
            zt_list()

        elif sub == "dump":
            zt_dump()

        else:
            usage()

    elif cmd == "control":
        if len(sys.argv) != 2:
            usage()
        control_mode()

    elif cmd == "set":
        if len(sys.argv) != 3:
            usage()

        save_target(sys.argv[2])

    else:
        usage()


def load_target():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_TARGET

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            return data.get("target", DEFAULT_TARGET)
    except Exception:
        return DEFAULT_TARGET


def save_target(target):
    if not target.startswith(("http://", "https://")):
        target = "http://" + target

    target = target.rstrip("/")
    parsed = urlparse(target)

    if parsed.port is None:
        target = f"{parsed.scheme}://{parsed.hostname}:3050"

    with open(CONFIG_FILE, "w") as f:
        json.dump({"target": target}, f, indent=4)

    good(f"Target set to {target}")

if __name__ == "__main__":
    main()