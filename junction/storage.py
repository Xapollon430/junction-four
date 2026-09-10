"""Durable consensus state and append-only road events."""

import json
from pathlib import Path

from .config import DATA_DIR, ROADS

EMPTY_CONSENSUS = {"currentTerm": 0, "votedFor": None, "log": [], "commitIndex": -1}


class RoadStorage:
    def __init__(self, road_id: str, base_directory: Path = DATA_DIR):
        self.directory = Path(base_directory) / road_id
        self.consensus_file = self.directory / "consensus.json"
        self.event_file = self.directory / "events.jsonl"
        self.directory.mkdir(parents=True, exist_ok=True)

    def load_consensus(self) -> dict:
        if not self.consensus_file.exists():
            return dict(EMPTY_CONSENSUS)
        try:
            value = json.loads(self.consensus_file.read_text(encoding="utf-8"))
            valid = (
                isinstance(value.get("currentTerm"), int)
                and value["currentTerm"] >= 0
                and (value.get("votedFor") is None or value["votedFor"] in ROADS)
                and isinstance(value.get("log"), list)
                and isinstance(value.get("commitIndex"), int)
            )
            if not valid:
                raise ValueError("invalid consensus state")
            return value
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not load {self.consensus_file}: {error}") from error

    def save_consensus(self, state: dict) -> None:
        temporary = self.consensus_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary.replace(self.consensus_file)

    def append_event(self, event: dict) -> None:
        with self.event_file.open("a", encoding="utf-8") as output:
            output.write(json.dumps(event, separators=(",", ":")) + "\n")
