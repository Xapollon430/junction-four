#!/usr/bin/env python3
"""Check queue bounds when the observer is reachable."""

import json
import os
from urllib.request import urlopen

from antithesis.assertions import always

observer = os.getenv("OBSERVER_URL", "http://visualizer:8080")
try:
    with urlopen(f"{observer}/api/state", timeout=2) as response:
        state = json.load(response)
    queues = {node["id"]: node["queueLength"] for node in state["nodes"].values()}
    always(all(length <= 20 for length in queues.values()), "Reported queues never exceed capacity", {"queues": queues})
except OSError as error:
    print(f"[workload] observer unavailable: {error}", flush=True)
