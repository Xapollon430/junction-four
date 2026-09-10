"""Small leader election and replicated log used to order phases."""

import time
from collections.abc import Callable

from antithesis.assertions import always, sometimes

from .config import ELECTION_MAX_MS, ELECTION_MIN_MS, HEARTBEAT_MS, ROADS, random_between

MAJORITY = len(ROADS) // 2 + 1


def now_ms() -> int:
    return int(time.time() * 1000)


class Consensus:
    def __init__(self, road_id: str, network, storage, apply_command: Callable):
        self.id = road_id
        self.network = network
        self.storage = storage
        self.apply_command = apply_command
        saved = storage.load_consensus()
        self.current_term = saved["currentTerm"]
        self.voted_for = saved["votedFor"]
        self.log = saved["log"]
        self.commit_index = min(saved["commitIndex"], len(self.log) - 1)
        self.last_applied = -1
        self.role = "follower"
        self.leader_id = None
        self.votes: set[str] = set()
        self.next_index: dict[str, int] = {}
        self.match_index: dict[str, int] = {}
        self.election_deadline = 0
        self.last_heartbeat_sent_at = 0
        self.on_event = None
        self.on_synchronized = None
        self.replay()
        self.reset_election_deadline()

    def replay(self) -> None:
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            self.apply_command(self.log[self.last_applied]["command"], self.last_applied, False)

    def persist(self) -> None:
        self.storage.save_consensus({
            "currentTerm": self.current_term,
            "votedFor": self.voted_for,
            "log": self.log,
            "commitIndex": self.commit_index,
        })

    async def emit_event(self, kind: str, details: dict) -> None:
        if self.on_event:
            await self.on_event(kind, details)

    async def synchronized(self) -> None:
        if self.on_synchronized:
            await self.on_synchronized()

    def reset_election_deadline(self) -> None:
        self.election_deadline = now_ms() + random_between(ELECTION_MIN_MS, ELECTION_MAX_MS)

    async def tick(self, now: int) -> None:
        if self.role == "leader":
            if now - self.last_heartbeat_sent_at >= HEARTBEAT_MS:
                await self.send_heartbeats()
        elif now >= self.election_deadline:
            await self.start_election()

    async def handle_message(self, peer_id: str, message: dict) -> bool:
        handlers = {
            "request_vote": self.handle_request_vote,
            "vote_response": self.handle_vote_response,
            "append_entries": self.handle_append_entries,
            "append_response": self.handle_append_response,
        }
        handler = handlers.get(message.get("type"))
        if not handler:
            return False
        await handler(peer_id, message)
        return True

    async def peer_connected(self, peer_id: str) -> None:
        if self.role == "leader":
            await self.send_append_entries(peer_id)

    async def become_follower(self, term: int, leader_id: str | None = None) -> None:
        term_changed = term > self.current_term
        if term_changed:
            self.current_term = term
            self.voted_for = None
        role_changed = self.role != "follower" or self.leader_id != leader_id
        self.role = "follower"
        self.leader_id = leader_id
        self.votes.clear()
        self.reset_election_deadline()
        if term_changed:
            self.persist()
        if role_changed:
            await self.emit_event("role_changed", {
                "role": self.role, "leaderId": leader_id, "term": self.current_term
            })

    async def start_election(self) -> None:
        self.role = "candidate"
        self.leader_id = None
        self.current_term += 1
        self.voted_for = self.id
        self.votes = {self.id}
        self.reset_election_deadline()
        self.persist()
        await self.emit_event("election_started", {"term": self.current_term})
        last_index = len(self.log) - 1
        await self.network.broadcast({
            "type": "request_vote",
            "term": self.current_term,
            "candidateId": self.id,
            "lastLogIndex": last_index,
            "lastLogTerm": self.log[last_index]["term"] if last_index >= 0 else 0,
        })

    async def handle_request_vote(self, peer_id: str, message: dict) -> None:
        term = message.get("term")
        if not isinstance(term, int):
            return
        if term < self.current_term:
            await self.network.send(peer_id, {"type": "vote_response", "term": self.current_term, "granted": False})
            return
        if term > self.current_term:
            await self.become_follower(term)
        last_index = len(self.log) - 1
        last_term = self.log[last_index]["term"] if last_index >= 0 else 0
        log_current = message.get("lastLogTerm", 0) > last_term or (
            message.get("lastLogTerm", 0) == last_term and message.get("lastLogIndex", -1) >= last_index
        )
        can_vote = self.voted_for is None or self.voted_for == message.get("candidateId")
        granted = can_vote and log_current
        if granted:
            self.voted_for = message.get("candidateId")
            self.reset_election_deadline()
            self.persist()
        await self.network.send(peer_id, {"type": "vote_response", "term": self.current_term, "granted": granted})

    async def handle_vote_response(self, peer_id: str, message: dict) -> None:
        if message.get("term", -1) > self.current_term:
            await self.become_follower(message["term"])
            return
        if self.role != "candidate" or message.get("term") != self.current_term or not message.get("granted"):
            return
        self.votes.add(peer_id)
        if len(self.votes) >= MAJORITY:
            await self.become_leader()

    async def become_leader(self) -> None:
        self.role = "leader"
        self.leader_id = self.id
        sometimes(True, "A leader is sometimes elected", {"road": self.id, "term": self.current_term})
        self.votes.clear()
        for peer_id in ROADS:
            if peer_id != self.id:
                self.next_index[peer_id] = len(self.log)
                self.match_index[peer_id] = -1
        await self.synchronized()
        await self.emit_event("role_changed", {"role": "leader", "leaderId": self.id, "term": self.current_term})
        await self.append({"type": "noop"}, f"noop-{self.current_term}-{self.id}")

    async def append(self, command: dict, entry_id: str) -> bool:
        if self.role != "leader":
            return False
        if any(entry["id"] == entry_id for entry in self.log):
            return True
        self.log.append({"id": entry_id, "term": self.current_term, "command": command})
        self.persist()
        await self.send_heartbeats()
        return True

    async def send_heartbeats(self) -> None:
        if self.role != "leader":
            return
        self.last_heartbeat_sent_at = now_ms()
        for peer_id in ROADS:
            if peer_id != self.id:
                await self.send_append_entries(peer_id)

    async def send_append_entries(self, peer_id: str) -> None:
        if self.role != "leader":
            return
        next_index = self.next_index.get(peer_id, len(self.log))
        previous = next_index - 1
        await self.network.send(peer_id, {
            "type": "append_entries",
            "term": self.current_term,
            "leaderId": self.id,
            "prevLogIndex": previous,
            "prevLogTerm": self.log[previous]["term"] if previous >= 0 else 0,
            "entries": self.log[next_index : next_index + 32],
            "leaderCommit": self.commit_index,
        })

    async def handle_append_entries(self, peer_id: str, message: dict) -> None:
        term = message.get("term")
        if not isinstance(term, int):
            return
        if term < self.current_term:
            await self.reject_append(peer_id, len(self.log) - 1)
            return
        if term > self.current_term or self.role != "follower" or self.leader_id != message.get("leaderId"):
            await self.become_follower(term, message.get("leaderId"))
        else:
            self.reset_election_deadline()
        previous = message.get("prevLogIndex", -1)
        if previous >= 0:
            entry = self.log[previous] if previous < len(self.log) else None
            if not entry or entry["term"] != message.get("prevLogTerm"):
                await self.reject_append(peer_id, min(previous - 1, len(self.log) - 1))
                return
        changed = False
        index = previous + 1
        for incoming in message.get("entries", []):
            existing = self.log[index] if index < len(self.log) else None
            if existing and (existing["term"] != incoming["term"] or existing["id"] != incoming["id"]):
                always(
                    index > self.commit_index,
                    "A committed log entry is never replaced",
                    {"road": self.id, "index": index, "commitIndex": self.commit_index},
                )
                self.log = self.log[:index]
                changed = True
            if index >= len(self.log):
                self.log.append(incoming)
                changed = True
            index += 1
        leader_commit = message.get("leaderCommit")
        if isinstance(leader_commit, int) and leader_commit > self.commit_index:
            self.commit_index = min(leader_commit, len(self.log) - 1)
            changed = True
        if changed:
            self.persist()
        self.apply_committed()
        if isinstance(leader_commit, int) and self.commit_index >= leader_commit:
            await self.synchronized()
        await self.network.send(peer_id, {
            "type": "append_response", "term": self.current_term,
            "success": True, "matchIndex": index - 1,
        })

    async def reject_append(self, peer_id: str, match_index: int) -> None:
        await self.network.send(peer_id, {
            "type": "append_response", "term": self.current_term,
            "success": False, "matchIndex": match_index,
        })

    async def handle_append_response(self, peer_id: str, message: dict) -> None:
        if message.get("term", -1) > self.current_term:
            await self.become_follower(message["term"])
            return
        if self.role != "leader" or message.get("term") != self.current_term:
            return
        if not message.get("success"):
            current = self.next_index.get(peer_id, len(self.log))
            self.next_index[peer_id] = max(0, min(current - 1, int(message.get("matchIndex", -1)) + 1))
            await self.send_append_entries(peer_id)
            return
        match = max(-1, int(message.get("matchIndex", -1)))
        self.match_index[peer_id] = match
        self.next_index[peer_id] = match + 1
        await self.advance_commit_index()
        if match < len(self.log) - 1:
            await self.send_append_entries(peer_id)

    async def advance_commit_index(self) -> None:
        for index in range(len(self.log) - 1, self.commit_index, -1):
            if self.log[index]["term"] != self.current_term:
                continue
            replicas = 1 + sum(
                1 for peer_id in ROADS
                if peer_id != self.id and self.match_index.get(peer_id, -1) >= index
            )
            if replicas < MAJORITY:
                continue
            self.commit_index = index
            self.persist()
            self.apply_committed()
            await self.send_heartbeats()
            break

    def apply_committed(self) -> None:
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied] if self.last_applied < len(self.log) else None
            always(
                entry is not None and self.last_applied <= self.commit_index,
                "Only committed log entries are applied",
                {"road": self.id, "lastApplied": self.last_applied, "commitIndex": self.commit_index},
            )
            if not entry:
                continue
            if entry.get("command", {}).get("type") == "phase":
                sometimes(True, "A phase is sometimes committed", {"road": self.id, "phaseId": entry["command"]["phaseId"]})
            self.apply_command(entry["command"], self.last_applied, True)

    def has_uncommitted_entries(self) -> bool:
        return len(self.log) - 1 > self.commit_index
