#!/usr/bin/env python3
"""Wait for a real consensus state before enabling fault injection."""

import json
import os
import time
from urllib.request import urlopen

from antithesis.lifecycle import setup_complete

observer = os.getenv("OBSERVER_URL", "http://visualizer:8080")
deadline = time.time() + 60
ready = False
while time.time() < deadline:
    try:
        with urlopen(f"{observer}/api/state", timeout=2) as response:
            state = json.load(response)
        nodes = list(state["nodes"].values())
        fresh = all(state["now"] - node["at"] < state["timing"]["peerFreshMs"] for node in nodes)
        ready = (
            len(nodes) == 4
            and fresh
            and sum(state["connections"].values()) == 4
            and all(node["readyForTraffic"] and node["commitIndex"] >= 0 for node in nodes)
            and len({node["commitIndex"] for node in nodes}) == 1
            and sum(node["role"] == "leader" for node in nodes) == 1
        )
        if ready:
            break
    except (OSError, ValueError):
        pass
    time.sleep(0.25)
if not ready:
    raise RuntimeError("cluster did not become ready")
setup_complete({"message": "Junction Four is ready"})
print("[workload] setup complete", flush=True)
while True:
    time.sleep(60)
