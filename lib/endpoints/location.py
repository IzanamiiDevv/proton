import json

from utils.request import request

def loc(action):

    if action == "open":
        print(json.dumps(request("/loc-open"), indent=4))

    elif action == "close":
        print(json.dumps(request("/loc-close"), indent=4))

    elif action == "status":
        data = request("/loc-status")
        print(f"Location Services: {'ENABLED' if data['enabled'] else 'DISABLED'}\n Latitude: {data['lat']}, Longitude: {data['lon']}\n Google Location: https://www.google.com/maps?q={data['lat']},{data['lon']}")