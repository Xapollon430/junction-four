#!/usr/bin/env python3
"""Add one car to a road chosen by Antithesis."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from antithesis.random import random_choice

road = random_choice(["north", "east", "south", "west"])
port = int(os.getenv("ROAD_API_PORT", "7200"))
request = Request(f"http://{road}:{port}/cars", data=b"{}", method="POST", headers={"Content-Type": "application/json"})
try:
    with urlopen(request, timeout=2) as response:
        print(json.dumps({"action": "add_car", "road": road, "status": response.status}), flush=True)
except HTTPError as error:
    if error.code != 429:
        print(json.dumps({"action": "add_car", "road": road, "unavailable": error.code}), flush=True)
except URLError as error:
    print(json.dumps({"action": "add_car", "road": road, "unavailable": str(error.reason)}), flush=True)
