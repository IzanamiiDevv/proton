# ---------------------------------------------------------------------------
# UIAutomator helpers (shared by all UI-driven automation, e.g. ZeroTier)
# ---------------------------------------------------------------------------

import os
import re
import time
import xml.etree.ElementTree as ET

from lib.executor.adb import adb
from utils.config import UI_DUMP_REMOTE, UI_DUMP_LOCAL

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
