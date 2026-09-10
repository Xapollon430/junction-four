"""One road's queue, signal, and local view of the shared phase."""

import asyncio
import time

from antithesis.assertions import always, sometimes

from .config import (
    ALL_RED_MS, AUTO_CARS, CAR_ARRIVAL_MAX_MS, CAR_ARRIVAL_MIN_MS,
    CAR_CROSSING_MS, CAR_INTERVAL_MS, GREEN_MS, PEER_FRESH_MS, PHASE_LEAD_MS,
    QUEUE_LIMIT, ROADS, STATUS_MS, YELLOW_MS, random_between,
)
from .consensus import Consensus
from .peer_network import PeerNetwork
from .phase import phase_ready_at, phase_stage
from .road_api import RoadApi
from .scheduler import choose_road
from .storage import RoadStorage


def now_ms() -> int:
    return int(time.time() * 1000)


class Road:
    def __init__(self, road_id: str):
        self.id = road_id
        self.storage = RoadStorage(road_id)
        self.current_phase = None
        self.round_robin_cursor = "north"
        self.ready_for_traffic = False
        self.peer_status: dict[str, dict] = {}
        self.car_queue: list[dict] = []
        self.dropped_cars = 0
        self.car_counter = 0
        self.event_counter = 0
        self.recent_events: list[dict] = []
        self.runtime = {"phaseId": None, "stage": "all_red", "light": "red", "lastHandledSlot": -1}
        self.last_status_sent_at = 0
        self.stopping = False
        self.tasks: set[asyncio.Task] = set()
        self.network = PeerNetwork(road_id, lambda: self.consensus.current_term if hasattr(self, "consensus") else 0)
        self.consensus = Consensus(road_id, self.network, self.storage, self.apply_command)
        self.api = RoadApi(self)
        self._bind_events()

    def _bind_events(self) -> None:
        self.network.on("listening", self._listening)
        self.network.on("protocol_error", lambda error: self.emit_road_event("protocol_error", {"message": str(error)}))
        self.network.on("peer_connected", self._peer_connected)
        self.network.on("peer_disconnected", lambda peer: self.emit_road_event("peer_disconnected", {"peerId": peer}))
        self.network.on("observer", self.initialize_observer)
        self.network.on("message", self.receive_peer_message)
        self.consensus.on_event = self._consensus_event
        self.consensus.on_synchronized = self._synchronized

    async def _listening(self, address: dict) -> None:
        print(f"[{self.id}] listening on {address['host']}:{address['port']}", flush=True)
        await self.emit_road_event("peer_started", {"term": self.consensus.current_term})
        if AUTO_CARS:
            self._task(self.car_arrival_loop())

    async def _peer_connected(self, peer_id: str) -> None:
        await self.emit_road_event("peer_connected", {"peerId": peer_id})
        await self.consensus.peer_connected(peer_id)

    async def _consensus_event(self, kind: str, details: dict) -> None:
        if kind == "role_changed" and details["role"] == "leader":
            self.peer_status.clear()
        await self.emit_road_event(kind, details)

    async def _synchronized(self) -> None:
        if self.ready_for_traffic:
            return
        self.ready_for_traffic = True
        await self.emit_road_event("peer_ready", {
            "leaderId": self.consensus.leader_id, "commitIndex": self.consensus.commit_index
        })

    def _task(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def start(self) -> None:
        await self.network.start()
        await self.api.start()
        self._task(self.control_loop())

    async def receive_peer_message(self, peer_id: str, message: dict) -> None:
        if await self.consensus.handle_message(peer_id, message):
            return
        if message.get("type") == "status" and self.consensus.role == "leader":
            self.peer_status[peer_id] = {**message["status"], "receivedAt": now_ms()}

    def apply_command(self, command: dict | None, index: int, announce: bool) -> None:
        if not command or command.get("type") != "phase":
            return
        self.current_phase = command
        self.round_robin_cursor = command["nextCursor"]
        if announce:
            self._task(self.emit_road_event("phase_committed", {
                "phaseId": command["phaseId"], "road": command["road"],
                "reason": command["reason"], "logIndex": index,
            }))

    async def car_arrival_loop(self) -> None:
        while not self.stopping:
            await asyncio.sleep(random_between(CAR_ARRIVAL_MIN_MS, CAR_ARRIVAL_MAX_MS) / 1000)
            await self.enqueue_car(source="automatic")

    async def enqueue_car(self, request_id=None, source: str = "unknown") -> dict:
        car_id = f"{self.id}-car-{now_ms()}-{self.car_counter}"
        self.car_counter += 1
        if len(self.car_queue) >= QUEUE_LIMIT:
            self.dropped_cars += 1
            await self.emit_road_event("car_dropped", {
                "carId": car_id, "requestId": request_id, "arrivalSource": source,
                "road": self.id, "queueLength": len(self.car_queue),
            })
            return {"accepted": False, "carId": car_id, "requestId": request_id, "queueLength": len(self.car_queue)}
        self.car_queue.append({"carId": car_id, "requestId": request_id, "arrivedAt": now_ms()})
        await self.emit_road_event("car_arrived", {
            "carId": car_id, "requestId": request_id, "arrivalSource": source,
            "road": self.id, "queueLength": len(self.car_queue),
        })
        return {"accepted": True, "carId": car_id, "requestId": request_id, "queueLength": len(self.car_queue)}

    async def control_loop(self) -> None:
        while not self.stopping:
            now = now_ms()
            await self.update_runtime(now)
            await self.consensus.tick(now)
            if self.consensus.role == "leader":
                await self.try_schedule_phase(now)
            if now - self.last_status_sent_at >= STATUS_MS:
                await self.send_status(now)
            await asyncio.sleep(0.05)

    async def update_runtime(self, now: int) -> None:
        phase = self.current_phase
        derived = phase_stage(phase, now)
        stage = derived["stage"] if self.ready_for_traffic else "recovering"
        light = derived["light"] if self.ready_for_traffic and phase and phase["road"] == self.id else "red"
        phase_id = phase["phaseId"] if phase else None
        changed = (self.runtime["phaseId"], self.runtime["stage"], self.runtime["light"]) != (phase_id, stage, light)
        if self.runtime["phaseId"] != phase_id:
            elapsed = now - phase["startAt"] if phase else -1
            self.runtime["lastHandledSlot"] = elapsed // CAR_INTERVAL_MS - 1 if elapsed > CAR_INTERVAL_MS else -1
        self.runtime.update(phaseId=phase_id, stage=stage, light=light)
        always(
            self.ready_for_traffic or light == "red",
            "A recovering road remains red",
            {"road": self.id, "readyForTraffic": self.ready_for_traffic, "light": light},
        )
        if changed:
            await self.emit_road_event("signal_changed", {"road": self.id, "light": light, "stage": stage, "phaseId": phase_id})
        if not self.ready_for_traffic or not phase or derived["stage"] != "green" or now < phase["startAt"]:
            return
        if phase["road"] == self.id:
            await self.release_car_for_current_slot(now, phase, light)

    async def release_car_for_current_slot(self, now: int, phase: dict, light: str) -> None:
        final_slot = (phase["greenMs"] - 1) // CAR_INTERVAL_MS
        current_slot = min(final_slot, (now - phase["startAt"]) // CAR_INTERVAL_MS)
        if current_slot <= self.runtime["lastHandledSlot"]:
            return
        for slot in range(self.runtime["lastHandledSlot"] + 1, current_slot + 1):
            self.runtime["lastHandledSlot"] = slot
            scheduled_at = phase["startAt"] + slot * CAR_INTERVAL_MS
            if now - scheduled_at > 250 or not self.car_queue:
                continue
            car = self.car_queue.pop(0)
            started_at = max(now, scheduled_at)
            permitted = self.ready_for_traffic and phase["road"] == self.id and light == "green"
            always(permitted, "A car starts only with committed green permission", {
                "road": self.id, "phaseId": phase["phaseId"], "phaseRoad": phase["road"],
                "light": light, "commitIndex": self.consensus.commit_index,
            })
            sometimes(True, "A car sometimes crosses", {"road": self.id, "phaseId": phase["phaseId"]})
            await self.emit_road_event("movement_started", {
                "entityId": car["carId"], "entityType": "car", "road": self.id,
                "queuedAt": car["arrivedAt"], "startedAt": started_at,
                "endsAt": started_at + CAR_CROSSING_MS, "phaseId": phase["phaseId"],
                "permission": {"road": phase["road"], "light": light},
            })

    async def try_schedule_phase(self, now: int) -> None:
        if self.consensus.has_uncommitted_entries() or now < phase_ready_at(self.current_phase):
            return
        previous_id = self.current_phase["phaseId"] if self.current_phase else "startup"
        statuses = self.collect_all_red_statuses(now, previous_id)
        if not statuses:
            return
        barrier = all(status["stage"] == "all_red" and status["allRedPhaseId"] == previous_id for status in statuses.values())
        always(barrier, "A new phase starts only after the all-red barrier", {"previousPhaseId": previous_id})
        demand = {road: statuses[road]["queueLength"] for road in ROADS}
        choice = choose_road(demand, self.round_robin_cursor)
        if not choice:
            return
        phase_id = f"{self.consensus.current_term}-{len(self.consensus.log)}-{now_ms()}"
        await self.consensus.append({
            "type": "phase", "phaseId": phase_id, "previousPhaseId": previous_id,
            "road": choice["road"], "reason": choice["reason"], "nextCursor": choice["nextCursor"],
            "startAt": now + PHASE_LEAD_MS, "greenMs": GREEN_MS,
            "yellowMs": YELLOW_MS, "allRedMs": ALL_RED_MS,
        }, f"phase-{phase_id}")

    def collect_all_red_statuses(self, now: int, previous_id: str) -> dict | None:
        statuses = {}
        for road in ROADS:
            status = self.make_status(now) if road == self.id else self.peer_status.get(road)
            if not status or now - status.get("receivedAt", status["at"]) > PEER_FRESH_MS:
                return None
            if status["stage"] != "all_red" or status["allRedPhaseId"] != previous_id:
                return None
            statuses[road] = status
        return statuses

    def make_status(self, now: int | None = None) -> dict:
        now = now if now is not None else now_ms()
        derived = phase_stage(self.current_phase, now)
        return {
            "id": self.id, "at": now, "term": self.consensus.current_term,
            "queueLength": len(self.car_queue), "droppedCars": self.dropped_cars,
            "light": derived["light"] if self.ready_for_traffic and self.current_phase and self.current_phase["road"] == self.id else "red",
            "stage": derived["stage"] if self.ready_for_traffic else "recovering",
            "phaseId": self.current_phase["phaseId"] if self.current_phase else None,
            "allRedPhaseId": derived["allRedPhaseId"] if self.ready_for_traffic else None,
        }

    def make_snapshot(self) -> dict:
        return {
            **self.make_status(), "role": self.consensus.role,
            "leaderId": self.consensus.leader_id, "commitIndex": self.consensus.commit_index,
            "logLength": len(self.consensus.log), "connectedPeers": self.network.connected_peer_ids(),
            "currentPhase": self.current_phase, "readyForTraffic": self.ready_for_traffic,
            "electionInMs": None if self.consensus.role == "leader" else max(0, self.consensus.election_deadline - now_ms()),
        }

    async def send_status(self, now: int) -> None:
        status = self.make_status(now)
        self.last_status_sent_at = now
        if self.consensus.role == "leader":
            self.peer_status[self.id] = {**status, "receivedAt": now}
        elif self.consensus.leader_id:
            await self.network.send(self.consensus.leader_id, {"type": "status", "status": status})
        await self.network.broadcast_to_observers({"type": "snapshot", "node": self.make_snapshot()})

    async def initialize_observer(self, writer: asyncio.StreamWriter) -> None:
        await self.network.send_to_observer(writer, {"type": "snapshot", "node": self.make_snapshot()})
        for event in self.recent_events[-40:]:
            await self.network.send_to_observer(writer, {"type": "event", "event": event})

    async def emit_road_event(self, kind: str, details: dict | None = None) -> None:
        event = {
            "eventId": f"{self.id}-{now_ms()}-{self.event_counter}", "type": kind,
            "source": self.id, "at": now_ms(), **(details or {}),
        }
        self.event_counter += 1
        self.recent_events.append(event)
        self.recent_events = self.recent_events[-200:]
        self.storage.append_event(event)
        await self.network.broadcast_to_observers({"type": "event", "event": event})

    async def stop(self) -> None:
        if self.stopping:
            return
        self.stopping = True
        await self.emit_road_event("peer_stopped", {"term": self.consensus.current_term})
        for task in list(self.tasks):
            task.cancel()
        await self.api.stop()
        await self.network.stop()
