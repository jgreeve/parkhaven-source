"""Explicit Windows desktop lifecycle/failure acceptance. Requires Playwright."""

import ctypes
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

from desktop_picker_smoke import ROOT, EXE, CALLBACK, user32, wintypes, class_name, free_port, wait_for_url, close_shell, await_json


class DesktopTemporaryDirectory(tempfile.TemporaryDirectory):
    """WebView2 releases its profile asynchronously after the host has exited."""

    def cleanup(self):
        end = time.monotonic() + 15
        while True:
            try:
                return super().cleanup()
            except OSError as error:
                if getattr(error, "winerror", None) not in (32, 145) or time.monotonic() >= end:
                    raise
                time.sleep(0.2)


def control(process, automation_id, invoke=False, select=False, value=False):
    windows = []

    @CALLBACK
    def find(window, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
        if pid.value == process.pid and user32.IsWindowVisible(window) and class_name(window).startswith("HwndWrapper"):
            windows.append(window)
        return True

    user32.EnumWindows(find, 0)
    if not windows:
        return ""
    script = (
        "$ErrorActionPreference = 'Stop'; [Console]::OutputEncoding = [Text.UTF8Encoding]::new(); "
        "Add-Type -AssemblyName UIAutomationClient; Add-Type -AssemblyName UIAutomationTypes; "
        f"$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]{windows[0]}); "
        "$condition = [System.Windows.Automation.PropertyCondition]::new("
        f"[System.Windows.Automation.AutomationElement]::AutomationIdProperty, '{automation_id}'); "
        "$element = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition); "
        + ("if ($element) { $element.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() }"
           if invoke else "if ($element) { $element.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select() }"
           if select else "if ($element) { $element.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).Current.Value }"
           if value else "if ($element) { $element.Current.Name }")
    )
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, encoding="utf-8", check=True, timeout=10)
    return result.stdout.strip()


def wait_message(process, expected, timeout=15):
    end = time.monotonic() + timeout
    text = ""
    while time.monotonic() < end:
        assert process.poll() is None, "Desktop exited instead of showing a recoverable error"
        text = control(process, "StartupMessage")
        if expected in text:
            return text
        time.sleep(0.2)
    raise AssertionError(f"Expected startup message containing {expected!r}; got {text!r}")


def launch(temp, **overrides):
    debug = free_port()
    environment = {**os.environ, "PARKHAVEN_STATE_DIR": str(temp / "state"),
                   "PARKHAVEN_PROJECTS_DIR": str(temp / "projects"),
                   "PARKHAVEN_APP_ROOT": str(ROOT),
                   "PARKHAVEN_PYTHON": str(ROOT / ".venv/Scripts/python.exe"),
                   "WEBVIEW2_USER_DATA_FOLDER": str(temp / "webview"),
                   "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": f"--remote-debugging-port={debug}",
                   **overrides}
    return subprocess.Popen([str(EXE)], env=environment), debug


def connect(playwright, process, port):
    wait_for_url(f"http://127.0.0.1:{port}/json/version", process)
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    for _ in range(100):
        pages = [page for context in browser.contexts for page in context.pages]
        if pages:
            break
        time.sleep(0.1)
    assert pages
    page = pages[0]
    expect(page.locator("#connection")).to_have_text("LOKAAL VERBONDEN", timeout=15000)
    return browser, page


def assert_port_closed(url):
    for _ in range(100):
        try:
            urlopen(url.rstrip("/") + "/api/health", timeout=0.5)
        except HTTPError:
            pass
        except OSError:
            return
        time.sleep(0.1)
    raise AssertionError("Owned backend still listening after desktop exit")


def stop(process):
    if process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
        process.wait(timeout=10)


def main():
    with DesktopTemporaryDirectory(prefix="parkhaven-lifecycle-", dir=Path(tempfile.gettempdir()) / "opencode") as directory:
        temp = Path(directory)
        # Missing interpreter: useful message, retry button, and close without a backend.
        process, _ = launch(temp / "missing", PARKHAVEN_PYTHON=str(temp / "missing-python.exe"))
        try:
            assert "Logbestand:" in wait_message(process, "Python ontbreekt")
            assert control(process, "RetryStartup") == "Opnieuw proberen"
            close_shell(process)
        finally:
            stop(process)

        fake = temp / "fake-root"
        (fake / "app").mkdir(parents=True)
        (fake / "app/__init__.py").write_text("", encoding="utf-8")
        server = fake / "app/desktop_server.py"
        server.write_text("raise SystemExit(7)\n", encoding="utf-8")
        process, port = launch(temp / "retry", PARKHAVEN_APP_ROOT=str(fake))
        try:
            wait_message(process, "backend stopte")
            # Repair the test fixture, then use the actual Retry button (same shell).
            server.write_text(
                f"import app\napp.__path__[:] = [{str(ROOT / 'app')!r}]\n"
                "from app.desktop_server import main\nraise SystemExit(main())\n", encoding="utf-8")
            control(process, "RetryStartup", invoke=True)
            with sync_playwright() as playwright:
                browser, page = connect(playwright, process, port)
                first_url = page.url
                assert await_json(page, "/api/health")["status"] == "ok"
                # Crash only the backend PID reported in this test session's own log.
                logs = "\n".join(path.read_text(encoding="utf-8") for path in (temp / "retry/state/logs").glob("*.log"))
                pid = int(re.findall(r"Started server process \[(\d+)\]", logs)[-1])
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, check=True)
                wait_message(process, "backend is onverwacht gestopt")
                control(process, "RetryStartup", invoke=True)
                page.wait_for_function("old => location.href !== old", arg=first_url, timeout=15000)
                expect(page.locator("#connection")).to_have_text("LOKAAL VERBONDEN")
                close_shell(process)
                assert_port_closed(page.url)
        finally:
            stop(process)

        # A backend which never publishes readiness times out and is stopped.
        server.write_text("import sys\nsys.stdin.readline()\nsys.stdin.read()\n", encoding="utf-8")
        process, _ = launch(temp / "timeout", PARKHAVEN_APP_ROOT=str(fake))
        try:
            wait_message(process, "niet binnen 30 seconden", timeout=50)
            close_shell(process)
        finally:
            stop(process)

        # Closing while readiness is pending must not leave the startup process running.
        process, _ = launch(temp / "early-close", PARKHAVEN_APP_ROOT=str(fake))
        try:
            wait_message(process, "Lokale backend starten")
            close_shell(process)
        finally:
            stop(process)

        # Independent sessions and owner crash: closing one must not stop the other.
        first, first_port = launch(temp / "first")
        second, second_port = launch(temp / "second")
        try:
            with sync_playwright() as playwright:
                _, first_page = connect(playwright, first, first_port)
                _, second_page = connect(playwright, second, second_port)
                first_url, second_url = first_page.url, second_page.url
                assert first_url != second_url
                close_shell(first)
                assert_port_closed(first_url)
                assert await_json(second_page, "/api/health")["status"] == "ok"
                second.kill()  # Kill only the shell: backend must observe pipe EOF itself.
                second.wait(timeout=10)
                assert_port_closed(second_url)
        finally:
            stop(first)
            stop(second)
        print("PASS: missing Python, early backend exit, retry, backend crash/retry, readiness timeout, close during startup, independent sessions, and owner-crash cleanup.")


if __name__ == "__main__":
    main()
