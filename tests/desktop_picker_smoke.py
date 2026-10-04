"""Explicit Windows/WebView2/native-dialog acceptance; needs optional Playwright.

Build the desktop shell first. The shell owns its isolated authenticated backend.
"""

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from urllib.error import HTTPError

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "desktop/ParkHaven.Desktop/bin/Release/net8.0-windows/ParkHaven.Desktop.exe"
user32 = ctypes.WinDLL("user32", use_last_error=True)
CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [CALLBACK, wintypes.LPARAM]
user32.EnumChildWindows.argtypes = [wintypes.HWND, CALLBACK, wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetDlgCtrlID.argtypes = [wintypes.HWND]
user32.GetDlgItem.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetDlgItem.restype = wintypes.HWND
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_url(url, process):
    for _ in range(150):
        assert process.poll() is None, f"Process exited early: {process.returncode}"
        try:
            with urlopen(url, timeout=1) as response:
                return json.load(response)
        except OSError:
            time.sleep(0.2)
    raise AssertionError(f"Startup timed out: {url}")


def class_name(window):
    text = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(window, text, len(text))
    return text.value


def close_shell(process):
    @CALLBACK
    def close(window, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
        if pid.value == process.pid and class_name(window).startswith("HwndWrapper") and user32.IsWindowVisible(window):
            user32.PostMessageW(window, 0x0010, 0, 0)  # WM_CLOSE: exercise normal async shutdown.
        return True
    user32.EnumWindows(close, 0)
    process.wait(timeout=25)


def finish_dialog(process, path=None):
    """Drive only the file dialog belonging to the shell started by this test."""
    for _ in range(100):
        windows = []

        @CALLBACK
        def find(window, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
            if pid.value == process.pid and class_name(window) == "#32770" and user32.IsWindowVisible(window):
                windows.append(window)
            return True

        user32.EnumWindows(find, 0)
        if windows:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Native file dialog did not open")
    dialog = windows[0]
    if path is None:
        user32.PostMessageW(dialog, 0x0111, 2, 0)  # WM_COMMAND / IDCANCEL
        return

    edits = []

    @CALLBACK
    def find_edit(window, _):
        if class_name(window) == "Edit" and user32.GetDlgCtrlID(window) in (1001, 1148) and user32.IsWindowVisible(window):
            edits.append(window)
        return True

    user32.EnumChildWindows(dialog, find_edit, 0)
    assert len(edits) == 1, f"Expected native filename field, found {len(edits)}"
    button = user32.GetDlgItem(dialog, 1)
    assert button, "Native Open button not found"
    text = ctypes.create_unicode_buffer(str(path))
    user32.SendMessageW(edits[0], 0x000C, 0, ctypes.addressof(text))  # WM_SETTEXT
    user32.PostMessageW(button, 0x00F5, 0, 0)  # BM_CLICK sends a normal button notification.


def main():
    assert EXE.is_file(), "Build the desktop shell in Release configuration first"
    with tempfile.TemporaryDirectory(prefix="parkhaven-picker-", dir=Path(tempfile.gettempdir()) / "opencode") as directory:
        temp = Path(directory)
        source = (temp / "ontwerp café 'variant A'.3dm").resolve()
        shutil.copy2(ROOT.parent / "ParkHaven_Analyzer_App_v0.2/ParkHaven_MVP.3dm", source)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        debug_port = free_port()
        projects = temp / "projects"
        shell = None
        try:
            shell = subprocess.Popen([str(EXE)], env={**os.environ,
                "PARKHAVEN_PROJECTS_DIR": str(projects),
                "PARKHAVEN_STATE_DIR": str(temp / "state"),
                "WEBVIEW2_USER_DATA_FOLDER": str(temp / "webview-profile"),
                "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": f"--remote-debugging-port={debug_port}",
            })
            wait_for_url(f"http://127.0.0.1:{debug_port}/json/version", shell)
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
                for _ in range(100):
                    pages = [page for context in browser.contexts for page in context.pages]
                    if pages:
                        break
                    time.sleep(0.1)
                assert pages, "WebView2 page not found"
                page = pages[0]
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                expect(page.locator("#browse-design")).to_be_visible(timeout=15000)
                url = page.url.rstrip("/")
                assert url.startswith("http://127.0.0.1:") and ":8765" not in url
                try:
                    urlopen(url + "/api/projects", timeout=2)
                except HTTPError as error:
                    assert error.code == 401
                else:
                    raise AssertionError("Unauthenticated desktop access was accepted")
                assert await_json(page, "/api/health")["status"] == "ok"
                field = page.locator("#design-path")
                field.fill("C:\\existing choice.3dm")
                page.locator("#browse-design").click()
                finish_dialog(shell)
                expect(field).to_have_value("C:\\existing choice.3dm")
                expect(page.locator("#form-status")).to_contain_text("geannuleerd")

                page.locator("#project-name").fill("Native picker acceptance")
                page.locator("#browse-design").click()
                finish_dialog(shell, source)
                expect(field).to_have_value(str(source))
                expect(page.locator("#form-status")).to_contain_text("Bestand gekozen")
                assert await_json(page, "/api/projects") == [], "Picking a file must not import it automatically"
                page.locator('#project-form button[type="submit"]').click()
                expect(page.locator("#form-status")).to_contain_text("veilig aangemaakt", timeout=15000)
                expect(page.locator(".open-project")).to_have_count(1)
                project = await_json(page, "/api/projects")[0]
                assert project["name"] == "Native picker acceptance"
                assert project["source"]["original_filename"] == source.name
                for path in (source, projects / project["project_id"] / "source/original-design.3dm",
                             projects / project["project_id"] / "working/parkhaven-design.3dm"):
                    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest

                # Seed explicit mock evidence to check authenticated report popups without launching Rhino.
                project_id = project["project_id"]
                await_json(page, f"/api/projects/{project_id}/placement", "PUT",
                           {"x": 0, "y": 0, "z": 0, "rotation_z_degrees": 0, "approved": True})
                job = await_json(page, f"/api/projects/{project_id}/analysis", "POST", {"launch_rhino": False})
                job_file = Path(job["data_dir"]).parent / "job.json"
                job["status"] = "completed"
                job_file.write_text(json.dumps(job), encoding="utf-8")
                (Path(job["data_dir"]) / "latest.json").write_text(
                    '{"bvo_m2":1000,"sight_pct":60,"indicative_cost_eur":1800000}', encoding="utf-8")
                page.locator(".open-project").click()
                page.locator("#report-link").click()
                # WebView2 replaces a provisional popup target with the host-owned view.
                report = None
                for _ in range(100):
                    page.wait_for_timeout(100)
                    reports = [candidate for context in browser.contexts for candidate in context.pages
                               if not candidate.is_closed() and "/report" in candidate.url]
                    if reports:
                        report = reports[0]
                        break
                assert report is not None, "Host-owned report window did not load"
                expect(report.locator("body")).to_contain_text("Opslaan als PDF")
                expect(report.locator("body")).to_contain_text("1.000,0 m2")
                assert not errors, errors
                close_shell(shell)
                try:
                    urlopen(url + "/api/health", timeout=1)
                except HTTPError:
                    raise AssertionError("Backend still listening after normal window close")
                except OSError:
                    pass
                else:
                    raise AssertionError("Backend still listening after normal window close")
            print("PASS: owned authenticated backend, native picker/import, Unicode paths, protected copies, authenticated report window and normal-close backend shutdown.")
        except Exception:
            for log in (temp / "state/logs").glob("*.log"):
                print(log.read_text(encoding="utf-8"), flush=True)
            raise
        finally:
            if shell is not None and shell.poll() is None:
                subprocess.run(["taskkill", "/PID", str(shell.pid), "/T", "/F"], capture_output=True, check=False)
                shell.wait(timeout=10)


def await_json(page, path, method="GET", data=None):
    return page.evaluate("""async ([path, method, data]) => {
      const response = await fetch(path, {method, ...(data === null ? {} : {
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)})});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    }""", [path, method, data])


if __name__ == "__main__":
    main()
