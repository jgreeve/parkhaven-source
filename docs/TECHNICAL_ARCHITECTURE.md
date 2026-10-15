# ParkHaven Studio Technical Architecture

**Estimated reading time:** 10-12 minutes
**Scope:** Current Windows tester build of ParkHaven Studio v0.1

## 1. What the system is

ParkHaven Studio is a local Windows desktop application that turns a Rhino `.3dm`
design into a repeatable Parkhaven massing analysis. It preserves the original model,
runs the existing Grasshopper calculation in an isolated Rhino process, displays the
results in a local 3D interface, optionally requests evidence-grounded AI advice, and
exports a print-ready PDF report.

The system is intentionally split into several processes. This keeps the desktop UI,
web API, and Rhino calculation lifecycle separate and lets the application identify
which Rhino instances it owns.

```text
ParkHaven.Desktop.exe                 .NET 8 WPF desktop shell
  |
  +-- WebView2                        HTML/CSS/JavaScript UI and Three.js viewer
  |
  +-- ParkHaven.Backend.exe           Packaged Python/FastAPI backend
        |
        +-- Rhino.exe                 One isolated child process per preview/run
        |     |
        |     +-- ParkHaven.Rhino.rhp Compiled Rhino plug-in
        |           |
        |           +-- Grasshopper   Isolated ParkHaven analysis definition
        |
        +-- HTTPS, optional           OpenAI-compatible AI provider
```

All application data and calculations remain local except the bounded text evidence
sent when the user explicitly requests AI advice. The current AI flow does not upload
the captured model images.

## 2. Main components

### Desktop shell

`ParkHaven.Desktop.exe` is a self-contained .NET 8 WPF application. It provides the
native application window, Windows file dialogs, WebView2, PDF export, diagnostics,
and ownership of the backend process.

At startup, the shell creates a random 256-bit session token and starts the backend on
an operating-system-selected loopback port. The token is passed through the backend's
private standard-input pipe, not through command-line arguments or a URL. WebView2
adds it as a request header without exposing it to the page's JavaScript. Closing the
window asks the backend to stop, waits for it, and closes only Rhino processes owned
by that backend session.

Key code: `desktop/ParkHaven.Desktop/`, especially `MainWindow.xaml.cs` and
`BackendProcess.cs`.

### Local backend

The backend is Python packaged as `ParkHaven.Backend.exe` with PyInstaller. FastAPI
serves both the static interface and the JSON API. Its responsibilities include:

- project creation and immutable source preservation;
- placement, unit interpretation, target, and repair records;
- preparation and monitoring of Rhino runs;
- validation and publication of analysis evidence;
- AI request construction and response validation;
- report HTML generation;
- shutdown, cancellation, and diagnostic state.

Desktop mode binds only to `127.0.0.1` on a random port. A separate fixed-port server
exists for browser development, but that unauthenticated development mode is not the
deployed security model.

Key code: `app/main.py`, `app/projects.py`, `app/workflow.py`, and
`app/desktop_server.py`.

### Browser interface and 3D viewer

The interface is a local single-page application written in HTML, CSS, and vanilla
JavaScript. Three.js renders metre-space scene meshes produced by the analysis. The UI
polls run state, displays progress, shows calculated layers, and creates four
controlled model views for evidence and reporting.

The viewer can display an attributed PDOK aerial, but that aerial is visual context
only. It is not imported into Rhino or used in deterministic calculations.

Key code: `app/static/app.js`, `app/static/viewer.js`, and `app/static/styles.css`.

### Rhino plug-in and Grasshopper analyzer

Every preview or analysis starts a new Rhino 8 process with a run-local model copy.
The `ParkHaven.Rhino.rhp` plug-in activates only when the process receives a valid
`PARKHAVEN_JOB_FILE` environment variable. Normal user-opened Rhino sessions therefore
do not run ParkHaven jobs.

The plug-in validates the job, locks it against duplicate execution, prepares the
geometry, applies approved units and placement, restores the fixed context, and loads
an isolated Grasshopper definition. Grasshopper solves once and publishes calculation
results and display meshes. Rhino and Grasshopper assemblies come from the installed
Rhino 8 application and are not redistributed.

The sibling `ParkHaven_Analyzer_App_v0.2` repository is the calculation reference,
not a second production server. Packaging takes its verified reference model,
Grasshopper definition, weather file, and locally vendored viewer assets. The legacy
analyzer dashboard and database are not part of the desktop runtime.

Key code: `rhino-plugin/`, plus the analyzer's `grasshopper/` components.

## 3. End-to-end data flow

### Step 1: Import and preserve the design

The user selects a `.3dm` file through the native picker. The backend creates a UUID
project, calculates the source SHA-256, and writes two copies:

- `source/original-design.3dm`: preserved and expected to remain byte-identical;
- `working/parkhaven-design.3dm`: the independent basis for future operations.

Both copies are verified against the source hash. If project creation fails midway,
the partial workspace is removed rather than exposed as a valid project.

### Step 2: Approve interpretation and placement

The project records translation in metres, rotation around Z, and the chosen model-unit
interpretation. This supports files whose coordinate values are metre-sized despite
incorrect unit metadata. Placement must be explicitly approved before analysis.

These transformations are applied only to run-local copies. The original and working
files are not overwritten by analysis.

### Step 3: Create an isolated run

The backend creates a new UUID run directory and snapshots every required input:

- the working design;
- approved placement, repair, and target records;
- the ParkHaven Grasshopper definition;
- the weather file;
- hashes for the model, definition, weather, and context.

This snapshot makes a completed run inspectable even after project settings change.
Only one preview or analysis may be active for a project at a time.

### Step 4: Prepare geometry in Rhino

The backend starts Rhino with the run-local design. The plug-in then:

1. interprets or corrects model units;
2. applies scale, Z rotation, and metre translation;
3. classifies visible, unlocked, valid solids as analytical design geometry;
4. keeps other renderable geometry as visual-only geometry;
5. replaces fixed reference layers from the hashed ParkHaven reference model;
6. writes stable object identifiers and `geometry-summary.json`.

Analytical and visual-only geometry are deliberately separated. Geometry can appear
in the viewer without silently affecting BVO, visibility, or cost calculations.

### Step 5: Solve Grasshopper

For a full analysis, the plug-in opens the run-local Grasshopper definition in an
isolated `GH_Document` and performs one solution. Runtime errors fail the run rather
than producing a misleading partial success.

The analyzer publishes:

- `latest.json`: BVO, visibility, indicative cost, and screening metrics;
- `scene.json`: metre-space, Z-up meshes for design, context, and analysis layers.

Completion requires finite core values and a non-empty scene. The Grasshopper document
is detached afterward so later manual Rhino edits cannot overwrite completed evidence.

### Step 6: Bind visual evidence

After completion, the viewer produces four controlled 768 x 512 PNG views: top,
overview, facade-side, and park-side. The backend validates dimensions, format, camera
metadata, visible layers, and size limits. It then binds the views by hash to the exact
scene, geometry summary, results, weather, placement, and site-context package.

Publication is atomic. If one of those inputs changes, old captures and downstream AI
advice are no longer accepted as current evidence.

### Step 7: Request optional AI advice

The backend derives a bounded text package from validated evidence. It includes
calculated metrics, labelled principal volumes, view-relative positions, and explicit
statements about unavailable site constraints. The user's API key exists only for that
request and is not stored in project files or logs.

An OpenAI-compatible endpoint returns structured JSON. The backend rejects output that
references unknown metrics, objects, or views, lacks the required design tests, or
states unsupported conclusions. Horizontal shifts, setbacks, widening, and rotation
may be proposed as exploratory sensitivity tests, but the advice cannot claim legal,
plot, access, tunnel, or infrastructure clearance.

Saved advice includes evidence hashes and policy version `site-constraints-v2`. A
report omits advice if either the evidence or policy no longer matches.

### Step 8: Generate the report

FastAPI creates print-oriented HTML from validated run data. Current grounded AI
advice and controlled images are included only when provenance checks pass. WebView2
uses its native print engine to write an A4 PDF to the path selected by the user.

## 4. Persistent data model

Project data defaults to `%LOCALAPPDATA%\ParkHaven\projects`:

```text
<project-uuid>/
  project.json
  placement.json
  repairs.json
  targets.json
  source/original-design.3dm
  working/parkhaven-design.3dm
  runs/<run-uuid>/
    job.json
    design.3dm
    ParkHaven_Analysis.ghx
    weather/<weather-file>.epw
    data/latest.json
    data/scene.json
    data/geometry-summary.json
    data/view-evidence.json
    data/view-evidence/<capture-uuid>/*.png
    ai-advice.json
```

JSON files describe state; SHA-256 hashes connect inputs and outputs. Writes that
publish evidence are atomic. This provides local provenance and drift detection, not
a cryptographically signed or tamper-proof audit ledger.

## 5. Security and trust boundaries

- **Desktop to backend:** random session token, private stdin delivery, authenticated
  same-origin requests, strict Host/Origin checks, and `no-store` responses.
- **WebView2:** external requests and navigation are blocked. The session credential is
  attached by native code rather than browser JavaScript.
- **Filesystem:** project and run identifiers must be canonical UUIDs, and plug-in
  paths must remain inside the run directory. Local files are not encrypted.
- **Rhino:** imported models execute in a full native Rhino process, not a sandbox.
  Process ownership, exact document matching, job environment, and run locking limit
  accidental cross-run execution.
- **AI provider:** external endpoints require HTTPS; only localhost may use HTTP.
  Redirects across origins are rejected. An optional private CA and certificate pin
  can be configured for one exact provider origin.
- **Reports:** external text is escaped, and stale or mismatched AI evidence is omitted.

## 6. Packaging and deployment

The tester installer is built by `packaging/build_tester.ps1`. It creates:

- a self-contained Windows x64 .NET desktop application;
- a Python 3.13 PyInstaller backend;
- the compiled Rhino plug-in;
- pinned analyzer assets and local Three.js modules;
- an Inno Setup per-user installer.

Installation uses `%LOCALAPPDATA%\Programs\ParkHaven Studio`, registers the Rhino
plug-in under the current user, and installs or updates WebView2. Rhino 8 must already
be installed and licensed. The current artifact is not Authenticode-signed.

## 7. Current architectural limits

- The calculation and reference context are Parkhaven-specific.
- There is no approved legal plot, ground datum, north transform, tunnel envelope,
  access route, or infrastructure constraint package.
- The PDOK aerial is provisionally aligned visual context, not survey evidence.
- Climate output represents a configured weather condition, not a complete annual
  comfort study; foundation output is screening, not geotechnical or structural design.
- AI receives derived text evidence, not the captured PNG pixels.
- A restarted backend cannot adopt or cancel a Rhino process started by the previous
  backend session.
- There is no automatic project retention or cleanup policy.
- Local hashes detect change but do not prevent a local user from modifying files.
- Release signing and EPW redistribution approval remain deployment concerns.

## 8. Architectural summary

The central design principle is **isolated, provenance-linked execution**. The desktop
owns the backend, the backend owns each Rhino process, and every run owns immutable
input snapshots plus hash-linked outputs. Grasshopper remains the numerical authority;
the web viewer presents its results; AI provides constrained hypotheses rather than
new calculations or site approval. This separation makes failures, stale evidence,
and unsupported claims easier to detect without modifying the user's source model.
