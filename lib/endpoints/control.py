# ---------------------------------------------------------------------------
# Interactive control mode — drive the device node-by-node off a live dump
# ---------------------------------------------------------------------------

import json
import re

from utils.status import info, good, bad, warn, BLUE, RESET
from utils.uiautomator import dump_ui, tap_node, input_text, wait_for_focus, press_home, press_back


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