"""Real native developer tab, phase updates, unresponsive backend and crash evidence."""

import ctypes
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

from playwright.sync_api import sync_playwright, expect

from desktop_lifecycle_smoke import launch, connect, control, close_shell, stop, ROOT, await_json, wait_message, DesktopTemporaryDirectory


def wait_control(process, name, contains, value=False, timeout=15):
    text = ""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        assert process.poll() is None, "Desktop exited"
        text = control(process, name, value=value)
        if contains in text:
            return text
        time.sleep(0.2)
    raise AssertionError(f"{name}: expected {contains!r}, got {text!r}")


def main():
    with DesktopTemporaryDirectory(prefix="parkhaven-developer-", dir=Path(tempfile.gettempdir()) / "opencode") as folder:
        temp = Path(folder)
        # Test-only launcher injects artificial credentials to exercise native log redaction.
        fake = temp / "root"
        (fake / "app").mkdir(parents=True)
        (fake / "app/__init__.py").write_text("", encoding="utf-8")
        (fake / "app/desktop_server.py").write_text(
            f"import app,sys,asyncio\napp.__path__[:] = [{str(ROOT / 'app')!r}]\n"
            "from app.desktop_server import serve,read_configuration\nconfig=read_configuration(sys.stdin)\n"
            "print('Authorization: Bearer FAKE-CREDENTIAL; api_key=FAKE-API-KEY',file=sys.stderr,flush=True)\n"
            "print(config['token'],file=sys.stderr,flush=True)\nasyncio.run(serve(config,sys.stdin))\n", encoding="utf-8")
        shell, port = launch(temp, PARKHAVEN_APP_ROOT=str(fake))
        suspended = None
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        nt = ctypes.WinDLL("ntdll")
        nt.NtSuspendProcess.argtypes = nt.NtResumeProcess.argtypes = [ctypes.c_void_p]
        try:
            with sync_playwright() as playwright:
                _, page = connect(playwright, shell, port)
                source = temp / "sample.3dm"
                source.write_bytes(b"diagnostic test import")
                project = await_json(page, "/api/projects", "POST", {"design_path": str(source), "name": "Developer test"})
                project_id = project["project_id"]
                await_json(page, f"/api/projects/{project_id}/placement", "PUT",
                           {"x": 0, "y": 0, "z": 0, "rotation_z_degrees": 0, "approved": True})
                job = await_json(page, f"/api/projects/{project_id}/analysis", "POST", {"launch_rhino": False})
                backend_pid = await_json(page, "/api/developer/status")["process_id"]
                job_file = Path(job["data_dir"]).parent / "job.json"

                # Switching tabs must preserve the imported project form state.
                page.locator("#project-name").fill("unsaved form value")
                control(shell, "DeveloperTab", select=True)
                wait_control(shell, "DeveloperBackendStatus", "Actief")
                wait_control(shell, "DeveloperRunDetails", "Voorbereid", value=True)
                control(shell, "WorkspaceTab", select=True)
                expect(page.locator("#project-name")).to_have_value("unsaved form value")
                control(shell, "DeveloperTab", select=True)
                for state, label in (("preparing_model", "Model voorbereiden"), ("solving", "Grasshopper rekent")):
                    job["status"] = state
                    job.update(progress_step="test_substep", progress_detail="Test: referentieobject 23 invoegen",
                               step_seconds={"classify_design": 0.125})
                    job_file.write_text(json.dumps(job), encoding="utf-8")
                    wait_control(shell, "DeveloperRunDetails", label, value=True)
                    details = wait_control(shell, "DeveloperRunDetails", "referentieobject 23", value=True)
                    assert "classify_design:" in details
                wait_control(shell, "DeveloperRunSummary", "1 actief")
                job.update(status="failed", error="Test: mesh is niet gesloten.", warnings=["Test: visual-only object."])
                job_file.write_text(json.dumps(job), encoding="utf-8")
                details = wait_control(shell, "DeveloperRunDetails", "mesh is niet gesloten", value=True)
                assert "visual-only object" in details and job["run_id"] in details

                # Suspend only this test shell's authenticated backend process.
                suspended = kernel.OpenProcess(0x0800, False, backend_pid)
                assert suspended and nt.NtSuspendProcess(suspended) == 0
                wait_control(shell, "DeveloperBackendStatus", "Geen HTTP-antwoord")
                wait_control(shell, "DeveloperNotice", "dit bewijst geen crash")
                assert nt.NtResumeProcess(suspended) == 0
                kernel.CloseHandle(suspended)
                suspended = None
                wait_control(shell, "DeveloperBackendStatus", "Actief")

                subprocess.run(["taskkill", "/PID", str(backend_pid), "/F"], capture_output=True, check=True)
                wait_control(shell, "DeveloperBackendStatus", "Gestopt")
                wait_control(shell, "DeveloperRunSummary", "niet live bevestigd")
                wait_control(shell, "DeveloperRunDetails", "mesh is niet gesloten", value=True)
                log = wait_control(shell, "DeveloperLog", "Backendproces afgesloten", value=True)
                assert "Started server process" in log and "[redacted]" in log
                assert "FAKE-CREDENTIAL" not in log and "FAKE-API-KEY" not in log
                assert not re.search(r"\b[0-9a-f]{64}\b", log)
                for path in (temp / "state/logs").glob("*.log"):
                    text = path.read_text(encoding="utf-8")
                    assert "FAKE-CREDENTIAL" not in text and "FAKE-API-KEY" not in text
                    assert not re.search(r"\b[0-9a-f]{64}\b", text)
                # The workspace retry screen remains accessible alongside diagnostics.
                control(shell, "WorkspaceTab", select=True)
                wait_message(shell, "backend is onverwacht gestopt")
                control(shell, "RetryStartup", invoke=True)
                expect(page.locator("#connection")).to_have_text("LOKAAL VERBONDEN", timeout=15000)
                control(shell, "DeveloperTab", select=True)
                wait_control(shell, "DeveloperBackendStatus", "Actief")
                close_shell(shell)
        finally:
            if suspended:
                nt.NtResumeProcess(suspended)
                kernel.CloseHandle(suspended)
            stop(shell)
    print("PASS: native Developer tab, live substeps/timings/errors, preserved form, HTTP timeout vs process exit, retained/redacted logs, retry, and profile cleanup.")


if __name__ == "__main__":
    main()
