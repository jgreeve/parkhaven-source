# Desktop shell

The .NET 8 WPF/WebView2 shell starts its own local backend and provides a native
Windows `.3dm` file picker. **Bladeren...** fills in the design path; **Project
aanmaken** performs the existing source-preserving import. Cancelling the dialog
keeps the previous path. In an ordinary browser the path can be entered manually.

## Build

Run from `ParkHaven_App_v0.1` with a .NET 8 SDK installed:

```powershell
dotnet build .\desktop\ParkHaven.Desktop\ParkHaven.Desktop.csproj -c Release
```

This development machine has a portable SDK:

```powershell
& "$env:TEMP\opencode\dotnet-sdk\dotnet.exe" build .\desktop\ParkHaven.Desktop\ParkHaven.Desktop.csproj -c Release
```

## Start

Run `setup_windows.cmd` once to prepare the Python environment, then start the
compiled executable directly (or create a Windows shortcut to it):

```powershell
.\desktop\ParkHaven.Desktop\bin\Release\net8.0-windows\ParkHaven.Desktop.exe
```

The shell requires the .NET 8 Windows Desktop Runtime and Microsoft Edge
WebView2 Runtime. No backend terminal or `start_app.cmd` is needed for desktop use.
It finds the application folder relative to the executable and runs
`.venv\Scripts\python.exe -m app.desktop_server` without a console window.

## Backend lifecycle and authentication

- The backend binds `127.0.0.1:0`; Windows selects and reserves a free port.
- A random 256-bit session token is sent through a private stdin pipe. It is never
  placed in command arguments, URLs, browser storage, project files or logs.
- The shell waits up to 30 seconds for startup and checks the authenticated health
  endpoint before opening the UI.
- WebView2 adds the session header to same-origin requests, including report
  windows. HTML, assets and API routes all require authentication. Requests with
  unexpected hosts/origins are rejected; external WebView requests are blocked.
- Startup failures show a Dutch message, a log path and **Opnieuw proberen**.
  Backend exits during use are also reported and can be retried.
- Closing the main window sends a private shutdown command and waits for the
  backend to exit. A nonresponsive owned backend is stopped after 15 seconds.
  The backend also watches pipe EOF so it exits if its desktop owner crashes.
- Normal desktop shutdown closes its app-owned Rhino sessions. Active runs are
  recorded as cancelled; completed evidence remains intact. Unrelated Rhino
  sessions and separately launched development servers are not owned by the shell.

Keep any manual edits you wish to retain out of the app-owned analysis session
before closing the desktop. Reconciliation of active jobs after a hard backend
crash is still pending; the Retry button restores the backend/UI connection.

Logs are stored in `%LOCALAPPDATA%\ParkHaven\logs\desktop-<session-id>.log`.
WebView2 uses separate profiles under `%LOCALAPPDATA%\ParkHaven\WebView2` so
simultaneous desktop windows have independent runtime state.

Development overrides:

| Variable | Purpose |
|---|---|
| `PARKHAVEN_APP_ROOT` | Application folder containing `app/desktop_server.py`. |
| `PARKHAVEN_PYTHON` | Full path to the Python interpreter; defaults to the app's `.venv`. |
| `PARKHAVEN_STATE_DIR` | Desktop logs/profile root; defaults to `%LOCALAPPDATA%\ParkHaven`. |
| `PARKHAVEN_PROJECTS_DIR` | Project workspace root, inherited by the owned backend. |

The former `PARKHAVEN_APP_URL` setting is superseded by owned random-port startup.
`start_app.cmd` remains an explicit, unauthenticated browser-development server on
port 8765. Installer/bundled-Python packaging is a later milestone.

## Verified native acceptance

### Developer diagnostics

The native **Developer** tab remains accessible even if the backend stops. It
shows process IDs/state, HTTP response time and last successful response, recent
run phases and Rhino substeps, measured step durations, errors/warnings and a
retained, redacted log. A two-second HTTP timeout is explicitly distinguished from
a known process exit; offline run details are labelled as last-known data.
Use **Diagnostiek kopiëren** or **Logmap openen** when investigating a run.
Switching tabs preserves the workspace form. Progress is stage/activity based,
not a fabricated completion percentage.

Close the desktop before rebuilding its executable on Windows.

### Acceptance commands

Release compilation passes with zero warnings/errors. The explicit smoke test
launches the real shell and its authenticated backend, plus the Windows file
dialog. It verifies selection, cancellation, paths with spaces/Unicode/apostrophes,
explicit import, SHA-256 source/copy preservation, authenticated report windows
and normal-close backend shutdown.

With the optional Playwright dependency installed:

```powershell
.\.venv\Scripts\python.exe .\tests\desktop_picker_smoke.py
.\.venv\Scripts\python.exe .\tests\desktop_lifecycle_smoke.py
.\.venv\Scripts\python.exe .\tests\desktop_developer_smoke.py
```

The lifecycle test covers missing Python, early backend failure, retry, a running
backend crash/retry, the readiness timeout, close during startup, independent
sessions and desktop-crash cleanup. Python regression tests also exercise real
backend subprocesses and authentication boundaries. Rhino shutdown status handling
is verified with mocked process boundaries; this milestone does not add a new
live Rhino solve test.

The Developer smoke covers substep/timing updates, errors/warnings, form retention,
an unresponsive-but-alive backend, process exit, retained/redacted logs and retry.
Cleanup waits up to 15 seconds for WebView2's asynchronous profile release and
fails if locks persist. The Dora/real-Rhino verification is documented separately
in `docs/RHINO_PLUGIN.md` and `progress.md`.

For verification on this machine, the sibling analyser's existing Python
environment supplied Playwright. The test uses its own processes, project root,
loopback ports and WebView2 profile. It enables a debugging port only for the
test-owned shell and cleans up afterward.
