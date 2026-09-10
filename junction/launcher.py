"""Run four roads and the visualizer for local development."""

import asyncio
import signal
import sys

from .config import ROADS, VISUALIZER_HOST, VISUALIZER_PORT


async def run_child(name: str, *args: str) -> None:
    while True:
        process = await asyncio.create_subprocess_exec(
            sys.executable, *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )

        async def relay(stream, destination):
            while line := await stream.readline():
                destination.write(f"[{name}] {line.decode()}")
                destination.flush()

        try:
            await asyncio.gather(relay(process.stdout, sys.stdout), relay(process.stderr, sys.stderr))
            code = await process.wait()
            print(f"[launcher] {name} exited ({code}); restarting in 1 second", file=sys.stderr)
            await asyncio.sleep(1)
        finally:
            if process.returncode is None:
                process.terminate()
                await process.wait()


async def main() -> None:
    tasks = [
        asyncio.create_task(run_child(road, "-m", "junction.node", "--id", road))
        for road in ROADS
    ]
    tasks.append(asyncio.create_task(run_child("visualizer", "-m", "junction.visualizer")))
    print(f"[launcher] visualizer: http://{VISUALIZER_HOST}:{VISUALIZER_PORT}")
    print("[launcher] Ctrl+C stops every process")
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stopped.set)
    await stopped.wait()
    for task in tasks:
        task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
