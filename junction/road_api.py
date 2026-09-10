"""Small HTTP API for health checks and workload car arrivals."""

import asyncio
import json

from .config import CONTROL


async def _reply(writer: asyncio.StreamWriter, status: int, body: dict) -> None:
    payload = json.dumps(body, separators=(",", ":")).encode()
    reason = {200: "OK", 201: "Created", 400: "Bad Request", 404: "Not Found", 429: "Too Many Requests"}[status]
    writer.write(
        f"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(payload)}\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n".encode()
        + payload
    )
    await writer.drain()
    writer.close()


class RoadApi:
    def __init__(self, road):
        self.road = road
        self.address = CONTROL[road.id]
        self.server: asyncio.Server | None = None

    async def start(self) -> None:
        self.server = await asyncio.start_server(
            self.handle, self.address["host"], self.address["port"]
        )
        print(f"[{self.road.id}] control API on {self.address['host']}:{self.address['port']}", flush=True)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode().strip()
            if not request_line:
                writer.close()
                return
            method, target, _ = request_line.split(" ", 2)
            content_length = 0
            while True:
                line = (await reader.readline()).decode()
                if line in ("\r\n", "\n", ""):
                    break
                name, value = line.split(":", 1)
                if name.lower() == "content-length":
                    content_length = min(int(value.strip()), 16_384)
            body = json.loads((await reader.readexactly(content_length)).decode()) if content_length else {}
            if method == "GET" and target == "/health":
                await _reply(writer, 200, {"id": self.road.id, "ready": self.road.ready_for_traffic, "role": self.road.consensus.role})
            elif method == "GET" and target == "/state":
                await _reply(writer, 200, self.road.make_snapshot())
            elif method == "POST" and target == "/cars":
                result = await self.road.enqueue_car(body.get("requestId"), "workload")
                await _reply(writer, 201 if result["accepted"] else 429, result)
            else:
                await _reply(writer, 404, {"error": "not found"})
        except (ValueError, json.JSONDecodeError, asyncio.IncompleteReadError) as error:
            await _reply(writer, 400, {"error": str(error)})

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
