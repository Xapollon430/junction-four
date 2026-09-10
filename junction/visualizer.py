"""Read-only checker, HTTP server, and browser event source."""

import asyncio
import json
import mimetypes
import signal
import time
from pathlib import Path
from urllib.parse import urlsplit

from antithesis.assertions import always

from .config import DATA_DIR, PEERS, PEER_FRESH_MS, ROADS, VISUALIZER_HOST, VISUALIZER_PORT
from .conflicts import intervals_overlap, movements_conflict
from .jsonl import read_json_lines, send_json

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT / "public"
VISUALIZER_DIR = DATA_DIR / "visualizer"
INCIDENT_FILE = VISUALIZER_DIR / "events.jsonl"
VISUALIZER_DIR.mkdir(parents=True, exist_ok=True)


def now_ms() -> int:
    return int(time.time() * 1000)


class Visualizer:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.connections = {road: False for road in ROADS}
        self.peer_writers: dict[str, asyncio.StreamWriter] = {}
        self.sse_clients: set[asyncio.StreamWriter] = set()
        self.seen_events: set[str] = set()
        self.recent_events: list[dict] = []
        self.recent_movements: list[dict] = []
        self.incidents: list[dict] = []
        self.incident_keys: set[str] = set()
        self.incident_counter = 0
        self.server: asyncio.Server | None = None
        self.tasks: set[asyncio.Task] = set()
        self.stopping = False

    def state(self) -> dict:
        return {
            "now": now_ms(), "nodes": self.nodes, "connections": self.connections,
            "incidents": self.incidents[-50:], "recentEvents": self.recent_events[-80:],
            "timing": {"peerFreshMs": PEER_FRESH_MS},
        }

    def _task(self, coroutine) -> None:
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def write_sse(self, writer: asyncio.StreamWriter, kind: str, payload: dict) -> bool:
        try:
            writer.write(f"event: {kind}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n".encode())
            await writer.drain()
            return True
        except (ConnectionError, asyncio.CancelledError):
            return False

    async def broadcast(self, kind: str, payload: dict) -> None:
        for writer in list(self.sse_clients):
            if not await self.write_sse(writer, kind, payload):
                self.sse_clients.discard(writer)
                writer.close()

    async def remember_event(self, event: dict) -> None:
        self.recent_events.append(event)
        self.recent_events = self.recent_events[-200:]
        await self.broadcast("road_event", event)

    async def record_incident(self, kind: str, message: str, details: dict, key: str) -> None:
        if key in self.incident_keys:
            return
        self.incident_keys.add(key)
        incident = {
            "incidentId": f"incident-{now_ms()}-{self.incident_counter}",
            "type": "incident", "kind": kind, "severity": "critical",
            "message": message, "at": now_ms(), **details,
        }
        self.incident_counter += 1
        self.incidents.append(incident)
        self.incidents = self.incidents[-200:]
        with INCIDENT_FILE.open("a", encoding="utf-8") as output:
            output.write(json.dumps(incident, separators=(",", ":")) + "\n")
        await self.broadcast("incident", incident)

    async def inspect_reported_state(self) -> None:
        current = now_ms()
        fresh = [node for node in self.nodes.values() if current - node["at"] < PEER_FRESH_MS]
        green = [node for node in fresh if node["light"] == "green"]
        always(
            len(green) <= 1,
            "At most one road reports green",
            {"roads": [node["id"] for node in green], "phaseIds": [node["phaseId"] for node in green]},
        )
        if len(green) > 1:
            roads = sorted(node["id"] for node in green)
            await self.record_incident(
                "concurrent_green", f"{' and '.join(roads)} both reported green.",
                {"roads": roads, "phaseIds": [node["phaseId"] for node in green]},
                f"concurrent:{':'.join(roads)}:{':'.join(sorted(str(node['phaseId']) for node in green))}",
            )

    @staticmethod
    def movement_authorized(event: dict) -> bool:
        permission = event.get("permission", {})
        return event.get("entityType") == "car" and permission.get("road") == event.get("road") and permission.get("light") == "green"

    async def process_movement(self, event: dict) -> None:
        current = now_ms()
        self.recent_movements = [move for move in self.recent_movements if move["endsAt"] >= current - 5000]
        authorized = self.movement_authorized(event)
        always(authorized, "Every car movement has matching green permission", {
            "entityId": event["entityId"], "road": event["road"],
            "phaseId": event["phaseId"], "permission": event.get("permission"),
        })
        if not authorized:
            await self.record_incident(
                "invalid_movement", f"{event['entityId']} entered without matching phase permission.",
                {"entities": [event["entityId"]], "phaseId": event.get("phaseId")},
                f"movement:{event['entityId']}",
            )
        collision = None
        for other in self.recent_movements:
            if other["entityId"] == event["entityId"] or not intervals_overlap(event, other):
                continue
            zone = movements_conflict(event, other)
            if not zone:
                continue
            collision = (other, zone)
            entities = sorted([event["entityId"], other["entityId"]])
            await self.record_incident(
                "car_car_collision", "Cars from two roads occupied the intersection at the same time.",
                {"entities": entities, "zone": zone, "phaseIds": [event["phaseId"], other["phaseId"]]},
                f"collision:{':'.join(entities)}:{zone}",
            )
        always(collision is None, "Conflicting car movements never overlap", {
            "entityId": event["entityId"],
            "otherEntityId": collision[0]["entityId"] if collision else None,
            "zone": collision[1] if collision else None,
        })
        self.recent_movements.append(event)

    async def handle_road_message(self, road: str, message: dict) -> None:
        if message.get("type") == "snapshot" and message.get("node", {}).get("id") == road:
            self.nodes[road] = message["node"]
            await self.inspect_reported_state()
            await self.broadcast("snapshot", {"road": road, "node": message["node"]})
            return
        event = message.get("event") if message.get("type") == "event" else None
        if not event or not event.get("eventId") or event["eventId"] in self.seen_events:
            return
        self.seen_events.add(event["eventId"])
        if len(self.seen_events) > 10_000:
            self.seen_events.pop()
        await self.remember_event(event)
        if event.get("type") == "movement_started":
            await self.process_movement(event)

    async def connect_to_road(self, road: str) -> None:
        while not self.stopping:
            self.connections[road] = False
            await self.broadcast("connection", {"road": road, "connected": False})
            address = PEERS[road]
            try:
                reader, writer = await asyncio.open_connection(address["host"], address["port"])
                self.peer_writers[road] = writer
                self.connections[road] = True
                await send_json(writer, {"type": "hello", "role": "observer", "id": "visualizer"})
                await self.broadcast("connection", {"road": road, "connected": True})
                async for message in read_json_lines(reader):
                    await self.handle_road_message(road, message)
            except (OSError, ConnectionError, ValueError):
                pass
            finally:
                self.connections[road] = False
                self.nodes.pop(road, None)
                writer = self.peer_writers.pop(road, None)
                if writer:
                    writer.close()
                await self.broadcast("connection", {"road": road, "connected": False})
            await asyncio.sleep(0.75)

    async def http_reply(self, writer: asyncio.StreamWriter, status: int, body: bytes, content_type: str) -> None:
        reason = {200: "OK", 403: "Forbidden", 404: "Not Found", 500: "Server Error"}[status]
        writer.write(
            f"HTTP/1.1 {status} {reason}\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\n"
            "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        writer.close()

    async def handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode().strip()
            if not request_line:
                writer.close()
                return
            _, target, _ = request_line.split(" ", 2)
            while (line := await reader.readline()) not in (b"\r\n", b"\n", b""):
                pass
            path = urlsplit(target).path
            if path == "/events":
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\n"
                    b"Connection: keep-alive\r\nAccess-Control-Allow-Origin: *\r\n\r\nretry: 1000\n\n"
                )
                await writer.drain()
                self.sse_clients.add(writer)
                await self.write_sse(writer, "state", self.state())
                return
            if path == "/api/state":
                await self.http_reply(writer, 200, json.dumps(self.state()).encode(), "application/json; charset=utf-8")
                return
            relative = "index.html" if path == "/" else path.lstrip("/")
            file_path = (PUBLIC_DIR / relative).resolve()
            if PUBLIC_DIR not in file_path.parents:
                await self.http_reply(writer, 403, b"Forbidden", "text/plain")
                return
            if not file_path.is_file():
                await self.http_reply(writer, 404, b"Not found", "text/plain")
                return
            content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in ("application/javascript", "image/svg+xml"):
                content_type += "; charset=utf-8"
            await self.http_reply(writer, 200, file_path.read_bytes(), content_type)
        except (ConnectionError, ValueError):
            writer.close()

    async def heartbeat(self) -> None:
        while not self.stopping:
            await asyncio.sleep(15)
            for writer in list(self.sse_clients):
                try:
                    writer.write(b": heartbeat\n\n")
                    await writer.drain()
                except ConnectionError:
                    self.sse_clients.discard(writer)

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_http, VISUALIZER_HOST, VISUALIZER_PORT)
        print(f"[visualizer] http://{VISUALIZER_HOST}:{VISUALIZER_PORT}", flush=True)
        for road in ROADS:
            self._task(self.connect_to_road(road))
        self._task(self.heartbeat())

    async def stop(self) -> None:
        self.stopping = True
        for task in list(self.tasks):
            task.cancel()
        for writer in [*self.peer_writers.values(), *self.sse_clients]:
            writer.close()
        if self.server:
            self.server.close()
            await self.server.wait_closed()


async def main() -> None:
    visualizer = Visualizer()
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stopped.set)
    await visualizer.start()
    await stopped.wait()
    await visualizer.stop()


if __name__ == "__main__":
    asyncio.run(main())
