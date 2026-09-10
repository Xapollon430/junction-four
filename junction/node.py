"""Start one road process."""

import argparse
import asyncio
import signal

from .config import ROADS
from .road import Road


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, choices=ROADS)
    road_id = parser.parse_args().id
    road = Road(road_id)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stopped.set)
    await road.start()
    await stopped.wait()
    await road.stop()


if __name__ == "__main__":
    asyncio.run(main())
