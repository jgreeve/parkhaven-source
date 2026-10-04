"""Owned desktop backend. Private stdin carries configuration and shutdown control."""

import asyncio
import json
import os
import re
import socket
import sys
import threading

import uvicorn

from .main import app
from .workflow import shutdown_owned_runs


def read_configuration(stream):
    config = json.loads(stream.readline(4096))
    if not isinstance(config, dict) or not re.fullmatch(r"[0-9a-f]{64}", config.get("token", "")):
        raise ValueError("Ongeldige desktopsessieconfiguratie.")
    if not re.fullmatch(r"[0-9a-f]{32}", config.get("session_id", "")):
        raise ValueError("Ongeldig desktopsessie-ID.")
    return config


async def serve(config, control):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # The OS selects and reserves the port in one operation: no free-port race.
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        authority = f"127.0.0.1:{listener.getsockname()[1]}"
        app.state.desktop_session = {"token": config["token"], "authority": authority, "origin": "http://" + authority}
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=0, access_log=False, log_level="info",
            timeout_graceful_shutdown=5,
        ))

        def watch_owner():
            # EOF also handles a crashed/killed desktop: it owns the pipe's only writer.
            for line in control:
                if line.strip() == "shutdown":
                    break
            server.should_exit = True

        threading.Thread(target=watch_owner, daemon=True).start()
        task = asyncio.create_task(server.serve(sockets=[listener]))
        try:
            while not server.started and not task.done() and not server.should_exit:
                await asyncio.sleep(0.02)
            if server.started and not server.should_exit:
                print(json.dumps({"event": "ready", "url": "http://" + authority,
                                  "session_id": config["session_id"], "process_id": os.getpid()}), flush=True)
            await task
        finally:
            shutdown_owned_runs()


def main():
    try:
        config = read_configuration(sys.stdin)
    except (ValueError, TypeError):
        # Never echo the private configuration, including in JSON decoder errors.
        print("Ongeldige desktopconfiguratie; start de backend vanuit ParkHaven Studio.", file=sys.stderr)
        return 1
    asyncio.run(serve(config, sys.stdin))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
