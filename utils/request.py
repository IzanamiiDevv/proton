import sys

from utils.config import load_target, load_token
from utils.status import bad

try:
    import requests
except ImportError:
    print("[!] requests module not installed")
    print("    pip install requests")
    sys.exit(1)

def request(endpoint):

    api = load_target()
    token = load_token()

    try:
        r = requests.get(api + endpoint, headers={"x-auth-token": token}, timeout=5)
        r.raise_for_status()
        return r.json()

    except Exception as e:
        bad(str(e))
        sys.exit(1)