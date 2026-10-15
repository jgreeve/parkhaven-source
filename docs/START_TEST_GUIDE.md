# ParkHaven v0.1 Start and Test Guide

## Current scope

This development build supports this workflow:

1. Create a project from a local `.3dm` file.
2. Preserve the original and create an isolated working copy.
3. Enter and approve a placement transform.
4. Start a run-local Rhino 8 and Grasshopper analysis.
5. Read BVO, visibility and indicative cost results.
6. Request Dutch advice from an OpenAI-compatible API.
7. Open a printable report and save it as PDF.

The current placement interface uses numeric X/Y/Z and rotation fields. The
interactive 3D placement gizmo, generated greenery, heat-resilience comparison
and AI image generation are not implemented yet.

## Requirements

- Windows 10 or Windows 11.
- Rhino 8 installed at `C:\Program Files\Rhino 8\System\Rhino.exe`.
- A licensed Rhino 8 session.
- The built and registered ParkHaven C# plug-in; see [RHINO_PLUGIN.md](RHINO_PLUGIN.md).
- Python 3 with the Windows `py` launcher.
- The sibling `ParkHaven_Analyzer_App_v0.2` folder with its verified
  `ParkHaven_MVP.3dm` and `ParkHaven_MVP.ghx` files.
- Internet access for first-time dependency setup and when requesting AI advice.

The imported design must contain at least one valid closed Brep or closed
extrusion. Open surfaces, curves, annotations and meshes may remain visible in
Rhino but are not accepted as BVO massing in the current runner.

## First-time setup

From `ParkHaven_App_v0.1`, run:

```bat
setup_windows.cmd
```

This creates `.venv` and installs FastAPI, Uvicorn and test dependencies.
Build/register the Rhino plug-in using `docs/RHINO_PLUGIN.md` before analysis.

## Start the application

After building the desktop shell (see `desktop/README.md`), run:

```bat
desktop\ParkHaven.Desktop\bin\Release\net8.0-windows\ParkHaven.Desktop.exe
```

The shell automatically starts its backend on an authenticated random loopback
port and waits for readiness. No separate terminal is needed. Closing the main
window stops its backend and app-owned Rhino sessions; unfinished runs are
cancelled. Completed calculation evidence is retained.

Startup errors show a Dutch explanation, log path and **Opnieuw proberen**.
The log directory is `%LOCALAPPDATA%\ParkHaven\logs`.

For browser-only development:

```bat
start_app.cmd
```

Then open <http://127.0.0.1:8765> and keep that development terminal open. This
explicit development server is separate from desktop sessions; Ctrl+C stops it.

## Test the user workflow

### 1. Import

1. Enter a project name.
2. In the desktop shell, select **Bladeren...** and choose a `.3dm` file. In a
   browser, enter its absolute path.
3. Select **Project aanmaken**.
4. Confirm that the project appears under **Projecten**.
5. Select **Verdergaan**.

Selecting a file only fills the path field. Import happens when you select
**Project aanmaken**. Cancelling the file dialog preserves the previous path.

### 2. Placement

1. Enter X, Y and Z translation in metres.
2. Enter rotation around the vertical axis in degrees.
3. Choose **Modeleenheid**. Keep **Bestandseenheid gebruiken** for correctly
   labelled files. If a metre-sized design was saved with millimetre metadata
   (for example, a 21 m building has coordinate height 21), choose
   **Meters — 1 = 1 m**. This is the correct selection for `test-ui-dora.3dm`.
4. Check the placement/unit approval box.
5. Select **Plaatsing opslaan**, then start a **new** analysis.

The source `.3dm` is never changed. Unit correction, rotation and translation are
applied only in Rhino memory during a run. Correctly authored millimetre files
are not enlarged automatically. Unsaved placement/unit changes prevent starting
an analysis; old runs retain their original inputs and results.

After installing this update, restart the desktop (or browser development server)
to load the new API field. Dora with metre coordinate interpretation and zero
placement produces approximately **30,460.4 m2 BVO**, **61.4% sight** and
**EUR 54,828,722** at EUR 1,800/m2. The result card shows that run's interpreted
units, factor and physical dimensions.

### 3. Rhino and Grasshopper analysis

1. Close or save unrelated Rhino work before testing.
2. Select **Analyse starten**.
3. Allow Rhino 8 to open in a new visible instance.
4. Wait while the status changes through model preparation and solving.
5. Confirm that BVO, visibility and cost appear after completion.
6. Confirm that **Laatste analyse** loads the design and reference layers. Test
   **Ontwerp**, **Alles**, **Reset**, **Boven**, **Voor** and **Zij**, then toggle
   the layers. The viewer uses metres and Rhino Z-up.
7. Save placement, select **3D-preview maken**, and switch to **Plaatsingspreview**.
   Test constrained XY movement, Z rotation, origin/design-center reference,
   **Herstel opgeslagen** and explicit placement save. Gizmo edits clear approval.
8. After a completed analysis, switch to **Laatste analyse** and select **Vier
   modelbeelden vastleggen**. Confirm that top, overview, facade-side and park-side
   evidence is stored for that run. This action is disabled for draft previews.

The completed-run mode remains immutable evidence. Camera orbit, layer visibility
and camera buttons never change placement or trigger a calculation. Preview gizmo
changes update only the numeric draft until explicitly saved, and still require a
new analysis for new metrics. World `(0,0)` is not a verified plot/survey point.
The deterministic-check panel reports scene extents, scale thresholds, relationship
to viewer world Z=0 and overlap with available reference extents. These are coordinate
checks only, not legal plot or approved-ground validation; see
`docs/CONTEXT_PROVENANCE.md`.
Controlled model images are ordinary renders of the loaded run scene, not generated
design proposals. `view-evidence.json` binds their hashes and cameras to the run's
scene, geometry summary, metrics and placement.
Geographic north, legal plot boundary and ground alignment are not yet verified;
the UI labels this explicitly. If the latest run is not completed, an older
completed run cannot yet be selected.

Every run gets its own copied Grasshopper definition and `data` directory. The
existing exporter therefore cannot overwrite another project's results.

The C# plug-in now starts analysis automatically, with a real baseline solve
verified on this machine. If the status remains at **Rhino wordt gestart**:

1. Leave the Rhino instance opened by the app running.
2. Run `ParkHavenAnalyze` in Rhino.
3. Wait for the run to finish and the application to refresh.

The Rhino process launched by the app already contains the required job
environment. Use **Analyse annuleren** to stop its analysis process. Startup
timeouts and Rhino exits are shown as failed runs; select **Analyse starten** to
retry with a new isolated run. Keep the desktop open during analysis. Recovery of
active jobs after a hard backend crash is still pending. Project data defaults to:

```text
%LOCALAPPDATA%\ParkHaven\projects
```

Set `PARKHAVEN_PROJECTS_DIR` before startup to use a development directory.

### 4. AI advice

After a completed run:

1. Select **Vier modelbeelden vastleggen** and wait until all images are stored.
2. Enter the provider base URL, for example `https://api.openai.com/v1`.
3. Enter an OpenAI-compatible chat model name that can return JSON.
4. Enter the API key.
5. Describe the design goal.
6. Select **Vraag advies**.

The advice action stays disabled until valid same-run model images exist. The
request includes bounded labelled geometry, verified view projections and unchanged
Grasshopper metrics, but does not upload the images. The provider has 120 seconds to
return a response. Replies with unknown metric, view or object references are rejected.
Text-only OpenAI-compatible chat models are supported.
For the official DeepSeek endpoint, ParkHaven explicitly disables thinking mode and
enables JSON output so hidden reasoning cannot consume the advice output budget.
Use a model ID returned by DeepSeek's model-list endpoint; current documented IDs
include `deepseek-flash` and `deepseek-v4-pro`.
Common equivalent response fields from local models are normalized, such as
`observatie`/`tekst`, `view_id`/`view_ids` and an omitted optional `object_ids` list.
This does not permit unknown evidence references.

The app labels the largest analytical masses as **Volume A**, **Volume B**, etc. and
derives their relative left/centre/right position separately for each controlled
camera. Captures colour those masses consistently and the report uses a matching
legend instead of projected point labels. A valid new advice response contains exactly
three prioritized design actions.
Each action must identify a labelled volume, geometric operation, view-anchored
direction, concrete test magnitude, design goal, hypothesized effect, trade-off and
Grasshopper metrics to recalculate. Vague actions and invented evidence are rejected.
If a concrete direction omits the view name but cites a valid view in its evidence,
the app adds that view anchor deterministically. Empty, truncated, refused and malformed
provider responses are reported in readable terms. Invalid replies are not retried
automatically, so a slow or billed provider is called only once per request.

No verified plot, access, tunnel or other infrastructure envelope is currently
available. The evidence package tells the provider this explicitly. Horizontal
relocation, footprint expansion and rotation may be suggested as exploratory
sensitivity tests, but they do not establish feasibility or clearance. Verify every
such test against authoritative site constraints before use. Aerial imagery alone is
not proof of a subsurface tunnel or legal clearance.

The printable report presents these actions first. Raw UUIDs and metric field names
are replaced by readable labels; technical provenance is separated from the main
advice, and the four evidence images are included as a compact gallery. Older saved
advice from before the site-constraint policy is omitted. Rerun the analysis, capture
the views and request new advice to produce the structured action cards and coloured
Volume A/B/C legend.

The viewer should show **PDOK-luchtfoto** beneath the model and the attribution
`Bron: Beeldmateriaal Nederland, via PDOK`. Use the checkbox and **Dekking** slider
to inspect the model against the image. This layer is visual-only: it does not
confirm ground level, legal plot or surveyed north. After this context update,
capture the four model images again before requesting AI advice; older captures
are intentionally treated as stale.

For a private AI server, use the endpoint supplied by its administrator. Configure
its certificate through the ignored origin-specific local trust profile and restart
the app. Use the server's API key and exact model ID. See [AI_TLS.md](AI_TLS.md)
for setup, certificate renewal and the distinction between TLS and authentication.

The API key is sent only with that request. It is not written to the project,
report, browser storage or application logs. External endpoints must use HTTPS;
plain HTTP is accepted only for localhost development.

### 5. PDF

1. Select **Rapport openen**.
2. Select **Opslaan als PDF**.
3. Choose the destination file. The desktop app creates an A4 PDF without browser
   headers or footers. Browser-only development falls back to the print dialog.

The A4 layout keeps the three headline metrics in one row, places screening values in
a compact table and keeps the four evidence images in a two-column grid. It separates
Grasshopper results from AI inference and omits unavailable results rather than
inventing them.

## Automated tests

Run:

```bat
.venv\Scripts\python.exe -m pytest -q
```

The tests use temporary projects and mocked external boundaries. They do not
launch Rhino and do not call a real AI provider.

Optional JavaScript syntax check when Node.js is installed:

```bat
node --check app\static\app.js
```

## Troubleshooting

- **Keur eerst de plaatsing goed:** save placement with the approval box checked.
- **Rhino 8 is niet gevonden:** set `PARKHAVEN_RHINO_EXE` to the installed
  `Rhino.exe` before starting the app.
- **Analysebestanden ontbreken:** set `PARKHAVEN_ANALYZER_ROOT` to the verified
  `ParkHaven_Analyzer_App_v0.2` folder.
- **Geen gesloten Breps of extrusies:** repair or convert the design geometry in
  Rhino; automatic geometry repair is not implemented yet.
- **Plug-in ontbreekt:** build/register it using `docs/RHINO_PLUGIN.md`.
- **Run blijft wachten:** use the manual `ParkHavenAnalyze` fallback above, then
  inspect `runs\<run-id>\job.json`, Rhino command history and Grasshopper warnings.
- **AI-verzoek mislukt:** verify endpoint, model access, key, HTTPS and provider
  OpenAI chat-completions compatibility.
