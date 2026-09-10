#!/usr/bin/env python3
"""Verify convergence after Antithesis has stopped faults."""

import json
import os
import time
from urllib.request import urlopen

from antithesis.assertions import always

observer = os.getenv("OBSERVER_URL", "http://visualizer:8080")
deadline = time.time() + 30
state = {"nodes": {}, "connections": {}}
recovered = False
while time.time() < deadline:
    try:
        with urlopen(f"{observer}/api/state", timeout=2) as response:
            state = json.load(response)
        nodes = list(state["nodes"].values())
        fresh = all(state["now"] - node["at"] < state["timing"]["peerFreshMs"] for node in nodes)
        recovered = (
            len(nodes) == 4
            and fresh
            and sum(state["connections"].values()) == 4
            and all(node["readyForTraffic"] for node in nodes)
            and sum(node["role"] == "leader" for node in nodes) == 1
            and len({node["commitIndex"] for node in nodes}) == 1
        )
        if recovered:
            break
    except (OSError, ValueError):
        pass
    time.sleep(0.25)
always(recovered, "The cluster converges after faults stop", {"nodeCount": len(state["nodes"])})
