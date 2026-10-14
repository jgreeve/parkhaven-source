# ParkHaven App v0.1

> Confidential proprietary project. Keep the source repository private. See
> [`docs/PRIVATE_GITHUB_ACCESS.md`](docs/PRIVATE_GITHUB_ACCESS.md) for separate
> developer and user distribution access.

Step-by-step owner setup: [`docs/GITHUB_SETUP_GUIDE.md`](docs/GITHUB_SETUP_GUIDE.md).

Windows desktop application under development for importing and positioning a
Rhino design on the Parkhaven site, running the existing Rhino/Grasshopper
analysis, requesting AI-assisted design advice and exporting a Dutch PDF report.

This folder is independent from `ParkHaven_Analyzer_App_v0.2`. The verified
analyser remains the calculation reference and is not modified by this app.

## Current runnable slice

The current slice provides:

- isolated project workspaces;
- `.3dm` source preservation and SHA-256 verification;
- an independent working copy for future repair and placement;
- versioned project, placement, repair and target records;
- a Dutch project creation/listing interface;
- a compiled WPF/WebView2 desktop shell with native `.3dm` file selection;
- automatic backend startup/shutdown, authenticated session ports and startup retry;
- native Developer diagnostics with retained logs, backend health and real Rhino substep timings;
- a local FastAPI application and API tests;
- persisted and approved numeric placement;
- per-project coordinate-unit correction for mislabelled models, applied only to analysis copies;
- compiled C# Rhino plug-in, automatic isolated Grasshopper solve and verified baseline results;
- run cancellation, process-exit detection and startup/solve timeouts;
- run result polling, evidence-grounded OpenAI-compatible text advice and native A4 PDF reporting;
- an attributed, locally pinned PDOK 2025 aerial beneath the existing 3D context, explicitly marked as provisional visual evidence.

Private-certificate AI connectivity can be configured through an ignored local
trust profile; see [AI TLS setup](docs/AI_TLS.md).

The desktop shell provides a native Windows file picker through **Bladeren...**.
The browser form accepts a local file path. See
[`desktop/README.md`](desktop/README.md) for desktop build and launch instructions.

## Run locally

```bat
setup_windows.cmd
desktop\ParkHaven.Desktop\bin\Release\net8.0-windows\ParkHaven.Desktop.exe
```

Run setup once; then launch the desktop executable directly. Build instructions
are in `desktop/README.md`. The desktop starts its own backend and closes it when
you exit. Project data defaults to
`%LOCALAPPDATA%\ParkHaven\projects`; set `PARKHAVEN_PROJECTS_DIR` to override it
for development.

For browser-only development, `start_app.cmd` still serves
<http://127.0.0.1:8765> separately from the authenticated desktop sessions.

Before analysis, build and register the Rhino plug-in following
[`docs/RHINO_PLUGIN.md`](docs/RHINO_PLUGIN.md). The SDK/tooling and live acceptance
commands are documented there.

## Tests

```bat
.venv\Scripts\python.exe -m pytest -q
```

See `progress.md` for verified status and the exact next task.
See `docs/START_TEST_GUIDE.md` for the complete start and manual test workflow.
