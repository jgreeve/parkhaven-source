# ParkHaven Studio (v0.1)

> **Proprietary, source-available project.** This source is published for evaluation
> only. All rights are reserved; see [`LICENSE`](LICENSE). It is **not** open source,
> and no permission to reuse, modify or redistribute is granted except by written
> agreement.

ParkHaven Studio is a Windows desktop application for the Parkhaven site. It imports a
Rhino design, runs the existing Rhino/Grasshopper massing analysis on an isolated copy,
shows the results in a local 3D viewer, can request evidence-grounded AI design advice,
and exports a printable A4 PDF report.

`ParkHaven_Analyzer_App_v0.2` is the calculation reference. ParkHaven Studio consumes
its verified model, Grasshopper definition and weather file but does not modify it.

---

## Start here

Pick the path that matches you.

| I want to... | Go to |
|---|---|
| **Test the app** (no coding) | [For testers](#for-testers) |
| **Build or change the code** | [For developers](#for-developers) |
| **Understand how it works** | [`docs/TECHNICAL_ARCHITECTURE.md`](docs/TECHNICAL_ARCHITECTURE.md) |
| **Report a problem** | [Feedback and issues](#feedback-and-issues) |

### Current availability

- Download the test build from the
  [**Releases**](https://github.com/jgreeve/parkhaven-source/releases) page:
  `ParkHaven-Setup-v0.1.0-win-x64.exe` with its SHA-256 checksum.
- The build is **unsigned** and has not been through clean-machine acceptance.
- Licensed **Rhino 8** is still required to run an analysis.

### Requirements (all testers)

- Windows 10 or Windows 11 (64-bit).
- **Rhino 8** installed and licensed at the standard location
  (`C:\Program Files\Rhino 8\System\Rhino.exe`).
- Microsoft Edge WebView2 Runtime (the installer adds it if missing).
- Internet access for first-time setup and when requesting AI advice.

---

## For testers

You do not need Python or .NET. You need the installer and Rhino 8.

### 1. Get the build

Download `ParkHaven-Setup-v0.1.0-win-x64.exe` from the
[**Releases**](https://github.com/jgreeve/parkhaven-source/releases) page and verify
the published SHA-256 checksum before installing.

> The installer is **unsigned**. Windows SmartScreen may warn about it. This is
> expected for the current tester build.

### 2. Install

1. Close Rhino and ParkHaven if they are open.
2. Run the installer. It installs per-user under
   `%LOCALAPPDATA%\Programs\ParkHaven Studio` and registers the Rhino plug-in.
3. It requires no administrator rights.

### 3. Run a test

1. Start **ParkHaven Studio** from the Start menu.
2. Create a project from a `.3dm` file (**Bladeren...** opens the Windows picker).
3. Enter and **approve** a placement transform.
4. Start the analysis and wait for Rhino/Grasshopper (about 30-60 seconds).
5. Review the three headline results: BVO, visibility and indicative cost.
6. Optionally request AI advice, then open the report and save it as PDF.

The full step-by-step walkthrough, including what to check at each step and
troubleshooting, is in [`docs/START_TEST_GUIDE.md`](docs/START_TEST_GUIDE.md).

### Unsigned-build and data-handling notes

- The installer and plug-in are **not Authenticode-signed**.
- Your `.3dm` source file is preserved unchanged; analysis runs on an isolated copy.
- The four model images stay on your machine. They are **not** uploaded.
- Your AI API key is used for a single request only and is never stored or logged.

### Known limitations (read before testing)

- No verified tunnel, plot boundary, ground level or access data exists. Placement and
  any movement suggestions are **exploratory**, not approval.
- The aerial image is provisional visual context, not survey evidence.
- Calculations are Parkhaven-specific massing screening, not regulatory or structural
  design.
- AI advice reasons over calculated text evidence, not the images.

---

## For developers

Build the desktop shell, backend and Rhino plug-in from source. This path requires more
tooling than testing.

### Prerequisites

- Windows 10 or Windows 11, licensed Rhino 8.
- Python 3 with the `py` launcher.
- .NET 8 SDK.
- The sibling `ParkHaven_Analyzer_App_v0.2` folder next to this repository, containing
  the verified `ParkHaven_MVP.3dm`, `ParkHaven_MVP.ghx` and weather assets.

### Setup and run from source

```bat
:: 1. Create the Python environment and install dev dependencies.
setup_windows.cmd

:: 2. Build and register the Rhino plug-in (see docs\RHINO_PLUGIN.md).
dotnet build .\rhino-plugin\ParkHaven.Rhino.csproj -c Release
.venv\Scripts\python.exe .\scripts\register_rhino_plugin.py

:: 3. Build the desktop shell.
dotnet build .\desktop\ParkHaven.Desktop\ParkHaven.Desktop.csproj -c Release

:: 4. Launch. The shell starts its own authenticated backend.
desktop\ParkHaven.Desktop\bin\Release\net8.0-windows\ParkHaven.Desktop.exe
```

`setup_windows.cmd` only prepares Python. It does **not** build the executable, so
steps 2-4 are required for a fresh clone. Build and launch details, plus the native
file picker and diagnostics, are in [`desktop/README.md`](desktop/README.md).

For browser-only development, `start_app.cmd` serves <http://127.0.0.1:8765>. This is an
unauthenticated development server, separate from desktop sessions.

Project data defaults to `%LOCALAPPDATA%\ParkHaven\projects`; override it with
`PARKHAVEN_PROJECTS_DIR`.

### Tests

```bat
.venv\Scripts\python.exe -m pytest -q
```

### Build the tester installer

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_tester.ps1
```

See [`packaging/README.md`](packaging/README.md). Output goes to `artifacts/`.

### Developer documents

- [`docs/TECHNICAL_ARCHITECTURE.md`](docs/TECHNICAL_ARCHITECTURE.md): how the system fits together.
- [`docs/RHINO_PLUGIN.md`](docs/RHINO_PLUGIN.md): plug-in build, register and acceptance.
- [`docs/CONTEXT_PROVENANCE.md`](docs/CONTEXT_PROVENANCE.md): what site context is and is not.
- [`docs/AI_TLS.md`](docs/AI_TLS.md): private-certificate AI connectivity.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md): rules for change and disclosure.
- [`docs/GITHUB_SETUP_GUIDE.md`](docs/GITHUB_SETUP_GUIDE.md): one-time owner/repository setup.

`progress.md` is the raw development journal. It is useful history but is **not** the
current tester status; use the sections above instead.

---

## Feedback and issues

Report problems to the project owner or in the private repository's Issues tab. Include:

- what you did, what you expected, and what happened;
- the app version and your Rhino 8 version;
- the **Diagnostiek kopiëren** output from the Developer tab, if available;
- screenshots of the viewer or report where helpful.

Do **not** attach proprietary `.3dm` models, API keys, session tokens or full logs
without explicit approval. See [`SECURITY.md`](SECURITY.md) for the private disclosure
route for security concerns.
