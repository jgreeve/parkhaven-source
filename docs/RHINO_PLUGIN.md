# Rhino 8 plug-in: build, setup and acceptance

## Verified milestone

`ParkHavenAnalyze` completes the baseline automatically on the development
machine. It reproduces BVO **17024.070833234422 m2**, visibility **65.12%**, cost
**EUR 30643327.49982196** and the baseline scene layer mesh counts/bounds.
Machine-readable evidence is in `rhino_plugin_verification.json`.

## Build and register

Requirements: installed/licensed Rhino 8 with Grasshopper, .NET 8 SDK and the
application's Python environment. The plug-in targets `net7.0-windows` for Rhino
8 compatibility; this machine runs it using Rhino's .NET 8 runtime. RhinoCommon,
GH_IO and Grasshopper are referenced from the installed Rhino directory and are
not bundled with the plug-in.

From `ParkHaven_App_v0.1`:

```powershell
dotnet build .\rhino-plugin\ParkHaven.Rhino.csproj -c Release
.\.venv\Scripts\python.exe .\scripts\register_rhino_plugin.py
```

This development machine has a portable SDK rather than an SDK on PATH:

```powershell
& "$env:TEMP\opencode\dotnet-sdk\dotnet.exe" build .\rhino-plugin\ParkHaven.Rhino.csproj -c Release
```

For a different Rhino installation, pass
`-p:RhinoInstallDir="D:\Applications\Rhino 8"` to `dotnet build` and set
`PARKHAVEN_RHINO_EXE` for the backend.

The output is `rhino-plugin/bin/Release/net7.0-windows/ParkHaven.Rhino.rhp`.
Registration writes only this plug-in's current-user Rhino 8 registry entry:

```text
HKCU\Software\McNeel\Rhinoceros\8.0\Plug-ins\7ff947f5-d80c-4be6-bc9b-88f77bdfe605
```

Both root `FileName` and `PlugIn\FileName` are set. The root value is needed for
Rhino's first-use registration. `LoadMode=1` loads the plug-in at startup. No
administrator rights are required. Registration points to the build directory;
rerun it if the application is moved. Close app-owned Rhino sessions before
rebuilding their loaded plug-in. A packaged installer remains a later task.

## Startup and manual fallback

1. The backend creates a run-local model and GHX, stores approved placement,
   target/repair snapshots and input hashes, then publishes `launch_requested`.
2. It starts `Rhino.exe /netcore /newinstance /nosplash <run-local-model>` directly.
   The child environment contains the absolute `PARKHAVEN_JOB_FILE` path.
3. The plug-in waits for Rhino's idle event and the matching active document,
   then invokes `ParkHavenAnalyze`. It does nothing in ordinary Rhino sessions
   without the job environment variable. `/runscript` is not needed.
4. The command locks the run, classifies geometry, applies placement, restores
   fixed context with unit conversion, loads the isolated GHX and solves it.
5. Completion requires finite BVO/visibility/cost results, a scene with layers,
   and no Grasshopper runtime errors. The GH document is detached afterward so
   manual model edits cannot overwrite completed calculation evidence.

If Rhino is ready but analysis has not started, enter **`ParkHavenAnalyze`** in
the Rhino instance launched by the app. The compatibility `run_analysis.py`
entry point now delegates to the same command. A completed, failed or cancelled
run cannot be executed twice: start a fresh run from the application.

An unregistered/missing plug-in is reported before launch. Startup times out
after 120 seconds; a run times out after 10 minutes from launch. Closing Rhino
during analysis produces a recoverable failed status. **Analyse annuleren**
terminates only the process owned by that run, then records `cancelled`.
Completed Rhino sessions remain open for inspection while the desktop is open.
Closing the desktop shuts down its backend and owned Rhino sessions; unfinished
runs are marked cancelled and completed evidence is preserved.

Backend process handles currently live in memory. Restart recovery/adoption of
already-running Rhino instances after a hard backend crash is not implemented:
keep the desktop open through analysis. Cancellation never kills a process using an unverified PID
from a previous backend session.

## Automated and real-Rhino verification

Fast tests use mocked process boundaries:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check .\app\static\app.js
```

The explicit browser smoke test uses installed Edge and the optional `playwright`
Python package. It verifies project switching, evidence clearing and start/cancel
controls using mocked analysis APIs:

```powershell
.\.venv\Scripts\python.exe .\tests\browser_workflow_smoke.py
```

On this development machine it was run with the sibling analyser's existing
Python environment, which already has Playwright installed. No analyser files
are changed by that test.

Explicit live acceptance (requires Rhino/licence; approximately 30 seconds here):

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_rhino_plugin.py
```

The script imports the baseline into an isolated temporary workspace, launches
Rhino, waits for completion, compares all three numerical results and all four
scene layer mesh counts/bounds, and checks SHA-256 preservation of the model,
definitions and baseline output files. It terminates only the Rhino it started
and retains the job and output paths in the evidence JSON for inspection.

Verified here: Rhino/Grasshopper `8.27.26019.16021`, Rhino .NET runtime `8.0.31`,
SDK `8.0.425`. Other Rhino versions, mixed-unit inputs and complex imported
geometry still require their planned acceptance cases.

## Imported model / preparation diagnostics (2026-09-30)

`test-ui-dora.3dm` exposed a warning-serialization exception that left the saved
status at `preparing_model`. Geometry preparation itself was fast. Explicit JSON
type metadata and warning nodes now let both successful status and failure status
serialize. Original command exceptions also go to `runner-error.log` beside
`job.json`; this file is useful if status publication itself fails.

Jobs now contain `progress_step`, `progress_detail`, `progress_at`, `step_seconds`
and `phase_started_at`. Object updates are throttled; the phase start does not reset
on each progress update. The Developer tab shows these diagnostics. Distinct steps
cover classification, reading/replacing reference layers, summary, redraw,
Grasshopper startup and solving.

Reproduce with an isolated copy (source and analyser hashes are checked; only
the test-owned Rhino is terminated):

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_rhino_import.py ..\test-ui-dora.3dm --output .\docs\rhino_dora_verification.json
dotnet run --project .\tests\rhino-job-serialization\JobSerialization.csproj -c Release
```

The second command is a small console regression using the actual job serializer,
compiled for net7 and rolled forward to the available runtime (8 on this machine).
It requires installed RhinoCommon but does not start Rhino. It checks the original
generic-warning failure path, failure recording with warnings and progress timing.

Live Dora execution completed in **37.26 seconds**, with **231 analytical / 2
visual-only** objects. Preparation took about **0.68 seconds**; GH startup took
**18.18 seconds**, solving **8.73 seconds**. The baseline numerical and scene
acceptance also still passes. Full evidence is in `rhino_dora_verification.json`;
the instrumented pre-fix timeout is retained in `rhino_dora_before.json`.

**Historical scale issue, now resolved below:** the initial Dora run declared
millimetres and produced BVO approximately `0.00424 m2`. This established that the
serialization fix worked, but its coordinate interpretation still needed correction.

After rebuilding, reopen the desktop and create a **new run**. Historical failed
or cancelled runs are preserved, not resumed or rewritten.

## Coordinate-unit correction and physical acceptance

Dora stores metre-sized coordinate values with millimetre metadata. Select
**Modeleenheid → Meters — 1 = 1 m** in the placement form, save its approval and
start a new run. `placement.model_units` defaults to `file`; other supported
interpretations are `meters`, `millimeters` and `centimeters`.

The run scales design/visual geometry and absolute tolerance by
`UnitScale(interpretedUnits, documentUnits)`, then rotates and translates.
Translation is always expressed in metres and converted to document units.
Context layers are replaced from the verified reference model using its own unit
metadata. No source or snapshot file is saved over. The job records original /
interpreted units, factor, dimensions and tolerances under `model_units`.

Dora now produces **30,460.40116279473 m2**, **61.4% sight**, and indicative cost
**EUR 54,828,722.09303051**. The GH algorithms and prices are unchanged.

```powershell
.\.venv\Scripts\python.exe .\scripts\verify_rhino_import.py ..\test-ui-dora.3dm --model-units meters --expected-bvo 30460.401162794733 --expected-sight 61.4 --output .\docs\rhino_dora_units_verification.json
.\.venv\Scripts\python.exe .\scripts\verify_rhino_unit_equivalence.py
```

The equivalence script requires optional `rhino3dm` solely to generate temporary
fixtures. It compares metre, true-mm and mislabelled-mm versions of a 10 × 20 × 9 m
box after nonzero translation and rotation. Each yields **600 m2 BVO**, **98.26%**
sight and **EUR 1,080,000**, with all scene bounds matching within 0.1 mm. True-mm
input uses factor 1; corrected-mm input uses factor 1000. This prevents the common
mistake of enlarging every millimetre model.

On this development machine the optional package is isolated under
`%TEMP%\opencode\rhino3dm-tools`; set `PYTHONPATH` to that directory when running
the equivalence script. It is not an application runtime dependency. Evidence is
in `rhino_unit_equivalence.json`; original source/analyser hash checks are retained
by each live run. The original numerical/scene baseline also still passes.
