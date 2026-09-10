"""TCP connections and message delivery, without consensus policy."""

import asyncio
import inspect

from .config import PEER_LISTEN_HOST, PEERS, ROADS
from .jsonl import read_json_lines, send_json


class PeerNetwork:
    def __init__(self, road_id: str, get_term):
        self.id = road_id
        self.address = PEERS[road_id]
        self.get_term = get_term
        self.peers: dict[str, asyncio.StreamWriter] = {}
        self.observers: set[asyncio.StreamWriter] = set()
        self.connecting: set[str] = set()
        self.details: dict[asyncio.StreamWriter, dict] = {}
        self.callbacks: dict[str, object] = {}
        self.server: asyncio.Server | None = None
        self.reconnect_task: asyncio.Task | None = None
        self.stopping = False

    def on(self, name: str, callback) -> None:
        self.callbacks[name] = callback

    async def emit(self, name: str, *args) -> None:
        callback = self.callbacks.get(name)
        if callback is None:
            return
        result = callback(*args)
        if inspect.isawaitable(result):
            await result

    async def start(self) -> None:
        self.server = await asyncio.start_server(
            self._accept, PEER_LISTEN_HOST, self.address["port"]
        )
        await self.emit("listening", {"host": PEER_LISTEN_HOST, "port": self.address["port"]})
        self.reconnect_task = asyncio.create_task(self._reconnect_loop())

    def _accept(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        asyncio.create_task(self.attach(reader, writer))

    async def attach(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, expected: str | None = None) -> None:
        self.details[writer] = {"role": None, "id": expected}
        await send_json(writer, {"type": "hello", "role": "peer", "id": self.id, "term": self.get_term()})
        try:
            async for message in read_json_lines(reader):
                await self.receive(writer, message)
        except (ConnectionError, ValueError) as error:
            await self.emit("protocol_error", error)
        finally:
            await self.remove(writer, expected)

    async def receive(self, writer: asyncio.StreamWriter, message: dict) -> None:
        if not isinstance(message, dict) or not isinstance(message.get("type"), str):
            return
        if message["type"] == "hello":
            await self.accept_hello(writer, message)
            return
        detail = self.details.get(writer)
        if detail and detail["role"] == "peer":
            await self.emit("message", detail["id"], message)

    async def accept_hello(self, writer: asyncio.StreamWriter, message: dict) -> None:
        detail = self.details[writer]
        if message.get("role") == "observer":
            detail.update(role="observer", id=message.get("id", "visualizer"))
            self.observers.add(writer)
            await self.emit("observer", writer)
            return
        peer_id = message.get("id")
        if message.get("role") != "peer" or peer_id not in ROADS or peer_id == self.id:
            writer.close()
            return
        detail.update(role="peer", id=peer_id)
        old = self.peers.get(peer_id)
        if old and old is not writer:
            old.close()
        self.peers[peer_id] = writer
        self.connecting.discard(peer_id)
        await self.emit("peer_connected", peer_id)

    async def remove(self, writer: asyncio.StreamWriter, expected: str | None) -> None:
        detail = self.details.pop(writer, None)
        if detail and detail["role"] == "peer" and self.peers.get(detail["id"]) is writer:
            self.peers.pop(detail["id"], None)
            await self.emit("peer_disconnected", detail["id"])
        self.observers.discard(writer)
        if expected:
            self.connecting.discard(expected)
        writer.close()

    async def _reconnect_loop(self) -> None:
        while not self.stopping:
            await self.connect_to_higher_peers()
            await asyncio.sleep(0.5)

    async def connect_to_higher_peers(self) -> None:
        own_index = ROADS.index(self.id)
        for peer_id in ROADS[own_index + 1 :]:
            if self.stopping or peer_id in self.peers or peer_id in self.connecting:
                continue
            self.connecting.add(peer_id)
            address = PEERS[peer_id]
            try:
                reader, writer = await asyncio.open_connection(address["host"], address["port"])
                asyncio.create_task(self.attach(reader, writer, peer_id))
            except OSError:
                self.connecting.discard(peer_id)

    async def send(self, peer_id: str, message: dict) -> bool:
        return await send_json(self.peers.get(peer_id), message)

    async def broadcast(self, message: dict) -> None:
        await asyncio.gather(
            *(self.send(peer_id, message) for peer_id in ROADS if peer_id != self.id)
        )

    async def send_to_observer(self, writer: asyncio.StreamWriter, message: dict) -> bool:
        return await send_json(writer, message)

    async def broadcast_to_observers(self, message: dict) -> None:
        for writer in list(self.observers):
            if not await send_json(writer, message):
                self.observers.discard(writer)

    def connected_peer_ids(self) -> list[str]:
        return sorted(self.peers)

    async def stop(self) -> None:
        self.stopping = True
        if self.reconnect_task:
            self.reconnect_task.cancel()
        for writer in [*self.peers.values(), *self.observers]:
            writer.close()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
