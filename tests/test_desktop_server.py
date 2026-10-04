"""Real subprocess checks for private-pipe startup and parent-disconnect cleanup."""

import json
import queue
import secrets
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("shutdown", ["command", "parent_eof"])
def test_actual_random_port_authenticated_startup_and_shutdown(shutdown):
    token, session = secrets.token_hex(32), uuid.uuid4().hex
    process = subprocess.Popen([sys.executable, "-u", "-m", "app.desktop_server"], cwd=ROOT,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        process.stdin.write(json.dumps({"token": token, "session_id": session}) + "\n")
        process.stdin.flush()
        lines = queue.Queue()
        threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True).start()
        line = lines.get(timeout=15)
        assert token not in line
        ready = json.loads(line)
        assert ready["event"] == "ready" and ready["session_id"] == session
        assert ready["url"].startswith("http://127.0.0.1:")
        with pytest.raises(HTTPError) as unauthorized:
            urlopen(ready["url"] + "/api/health", timeout=2)
        assert unauthorized.value.code == 401
        with urlopen(Request(ready["url"] + "/api/health", headers={"X-ParkHaven-Session": token}), timeout=2) as response:
            assert json.load(response)["status"] == "ok"
        if shutdown == "command":
            process.stdin.write("shutdown\n")
            process.stdin.flush()
        else:
            process.stdin.close()
        assert process.wait(timeout=15) == 0
        assert token not in process.stderr.read()
        with pytest.raises(OSError):
            urlopen(ready["url"] + "/api/health", timeout=1)
    finally:
        if process.poll() is None:
            if not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_bad_configuration_is_not_echoed_to_logs():
    secret = "secret-that-must-not-be-logged"
    result = subprocess.run([sys.executable, "-m", "app.desktop_server"], cwd=ROOT,
                            input=json.dumps({"token": secret}), capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert secret not in result.stdout + result.stderr
