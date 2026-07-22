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


def note_runtime(result):
    """Every command in this script drives the device over adb. The --adb
    flag doesn't change behavior today (adb is the only runtime implemented)
    but every command accepts it so the CLI surface stays consistent."""
    if result.get("--adb"):
        info("Runtime: adb")