"""Smoke-test the relocatable tester payload without relying on the source tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import queue
import secrets
import ssl
import subprocess
import threading
import uuid
from urllib.request import Request, urlopen


def fetch(url: str, token: str) -> bytes:
    request = Request(url, headers={"X-ParkHaven-Session": token})
    with urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"Onverwachte HTTP-status {response.status} voor {url}")
        return response.read()


def verify(payload: Path) -> None:
    payload = payload.resolve(strict=True)
    backend = payload / "backend" / "ParkHaven.Backend.exe"
    required = (
        payload / "ParkHaven.Desktop.exe",
        payload / "RhinoPlugin" / "ParkHaven.Rhino.rhp",
        backend,
        payload / "backend" / "_internal" / "analyzer" / "ParkHaven_MVP.3dm",
        payload / "backend" / "_internal" / "analyzer" / "ParkHaven_MVP.ghx",
        payload / "backend" / "_internal" / "analyzer" / "weather" / "NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw",
        payload / "backend" / "_internal" / "site-context" / "manifest.json",
    )
    missing = [str(path.relative_to(payload)) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Onvolledige payload: " + ", ".join(missing))
    forbidden = [path for pattern in ("*.pdb", "*.key", "*.pfx", "*.p12", ".env*")
                 for path in payload.rglob(pattern)]
    if forbidden:
        raise RuntimeError("Verboden bestanden in payload: " + ", ".join(map(str, forbidden)))

    config_root = payload / "backend" / "_internal" / "config"
    trust_config = (config_root / "ai-trust.local.json"
                    if (config_root / "ai-trust.local.json").is_file()
                    else config_root / "ai-trust.json")
    try:
        profiles = json.loads(trust_config.read_text(encoding="utf-8"))["endpoints"]
        if not isinstance(profiles, list):
            raise ValueError("endpoints is geen lijst")
        for profile in profiles:
            ca_file = (trust_config.parent / profile["ca_file"]).resolve(strict=True)
            if not ca_file.is_relative_to(config_root.resolve()):
                raise ValueError("ca_file valt buiten de configmap")
            if "PRIVATE KEY-----" in ca_file.read_text(encoding="ascii"):
                raise ValueError("ca_file bevat privésleutelmateriaal")
            context = ssl.create_default_context()
            context.load_verify_locations(cafile=str(ca_file))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, ssl.SSLError) as exc:
        raise RuntimeError("Ongeldige gebundelde AI-certificaatconfiguratie: " + str(exc)) from exc

    token, session_id = secrets.token_hex(32), uuid.uuid4().hex
    process = subprocess.Popen(
        [backend], cwd=backend.parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8",
    )
    try:
        assert process.stdin and process.stdout and process.stderr
        process.stdin.write(json.dumps({"token": token, "session_id": session_id}) + "\n")
        process.stdin.flush()
        lines: queue.Queue[str] = queue.Queue()
        threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
        ready = json.loads(lines.get(timeout=45))
        if ready.get("event") != "ready" or ready.get("session_id") != session_id:
            raise RuntimeError("Backend gaf geen geldige gereedmelding.")
        base = ready["url"]
        health = json.loads(fetch(base + "/api/health", token))
        if health != {"status": "ok", "version": "0.1.0"}:
            raise RuntimeError("Backend-healthcheck wijkt af.")
        for route in ("/", "/app.js", "/viewer-assets/three.module.min.js", "/api/site-context"):
            if not fetch(base + route, token):
                raise RuntimeError(f"Lege gebundelde resource: {route}")
        process.stdin.write("shutdown\n")
        process.stdin.flush()
        if process.wait(timeout=20) != 0:
            raise RuntimeError("Backend sloot niet schoon af.")
        stderr = process.stderr.read()
        if token in stderr:
            raise RuntimeError("Sessiegeheim is naar stderr geschreven.")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    verify(parser.parse_args().payload)
    print("ParkHaven tester payload: OK")
