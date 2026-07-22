
import json
from utils.status import good, bad
from utils.request import request

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