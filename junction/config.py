"""Shared topology and timing settings."""

import os
from pathlib import Path

from antithesis.random import get_random

ROADS = ("north", "east", "south", "west")
BASE_PEER_PORT = int(os.getenv("PEER_PORT_BASE", "7100"))
BASE_CONTROL_PORT = int(os.getenv("CONTROL_PORT_BASE", "7200"))
PEER_LISTEN_HOST = os.getenv("PEER_LISTEN_HOST", "127.0.0.1")
PEERS = {
    road: {
        "host": os.getenv(f"PEER_{road.upper()}_HOST", os.getenv("PEER_HOST", "127.0.0.1")),
        "port": BASE_PEER_PORT + index + 1,
    }
    for index, road in enumerate(ROADS)
}
CONTROL = {
    road: {
        "host": os.getenv("CONTROL_HOST", "127.0.0.1"),
        "port": int(os.getenv("CONTROL_PORT", str(BASE_CONTROL_PORT + index + 1))),
    }
    for index, road in enumerate(ROADS)
}
AUTO_CARS = os.getenv("AUTO_CARS", "true").lower() != "false"

GREEN_MS = int(os.getenv("GREEN_MS", "5000"))
YELLOW_MS = int(os.getenv("YELLOW_MS", "1500"))
ALL_RED_MS = int(os.getenv("ALL_RED_MS", "1000"))
CAR_CROSSING_MS = int(os.getenv("CAR_CROSSING_MS", "1000"))
CAR_INTERVAL_MS = int(os.getenv("CAR_INTERVAL_MS", "1000"))
HEARTBEAT_MS = int(os.getenv("HEARTBEAT_MS", "350"))
ELECTION_MIN_MS = int(os.getenv("ELECTION_MIN_MS", "1200"))
ELECTION_MAX_MS = int(os.getenv("ELECTION_MAX_MS", "2200"))
STATUS_MS = int(os.getenv("STATUS_MS", "300"))
PHASE_LEAD_MS = int(os.getenv("PHASE_LEAD_MS", "500"))
PEER_FRESH_MS = int(os.getenv("PEER_FRESH_MS", "1500"))
CAR_ARRIVAL_MIN_MS = int(os.getenv("CAR_ARRIVAL_MIN_MS", "6000"))
CAR_ARRIVAL_MAX_MS = int(os.getenv("CAR_ARRIVAL_MAX_MS", "12000"))
QUEUE_LIMIT = 20
HEAVY_QUEUE = 10
MAX_JSON_LINE_BYTES = 1_000_000
VISUALIZER_HOST = os.getenv("VISUALIZER_HOST", "127.0.0.1")
VISUALIZER_PORT = int(os.getenv("VISUALIZER_PORT", "8080"))
DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()


def random_between(minimum: int, maximum: int) -> int:
    """Draw when the choice is needed so Antithesis can steer it."""
    return minimum + get_random() % (maximum - minimum + 1)


def road_after(road: str) -> str:
    return ROADS[(ROADS.index(road) + 1) % len(ROADS)]
