"""Read and write one JSON object per TCP line."""

import asyncio
import json

from .config import MAX_JSON_LINE_BYTES


async def send_json(writer: asyncio.StreamWriter | None, message: dict) -> bool:
    if writer is None or writer.is_closing():
        return False
    writer.write((json.dumps(message, separators=(",", ":")) + "\n").encode())
    try:
        await writer.drain()
        return True
    except (ConnectionError, asyncio.CancelledError):
        return False


async def read_json_lines(reader: asyncio.StreamReader):
    while not reader.at_eof():
        line = await reader.readline()
        if not line:
            break
        if len(line) > MAX_JSON_LINE_BYTES:
            raise ValueError("JSON line exceeds limit")
        try:
            yield json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON line: {error}") from error
