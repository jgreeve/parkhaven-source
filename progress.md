# ParkHaven App Development Progress

Started: 2026-09-29

This is the continuity record for the new desktop application. Update it after
every significant implementation and verification stage.

Last synchronized: **2026-10-14**, after DeepSeek compatibility, native PDF export,
and evidence-integrity hardening. Product roadmap:
[`plan.md`](../ParkHaven_Analyzer_App_v0.2/docs/plan.md). The roadmap lives in the
analyser's documentation; the desktop implementation lives in this independent
`ParkHaven_App_v0.1` folder.
AI/ontwikkelaar instapgids: [`AI_WORK_GUIDE.md`](AI_WORK_GUIDE.md).

## Product boundary

- Windows 10/11 and Dutch-first UI.
- Installed and licensed Rhino 8 is required.
- Parkhaven site only for v1.
- Imported `.3dm` originals are preserved; changes require explicit consent.
- Grasshopper remains authoritative for deterministic calculations.
- AI advice must distinguish calculated evidence, model observations and inference.
- Conceptual AI-generated renders are outside the active scope for now. Accurate
  images of the real model remain required inputs for future visual AI advice.

## Current stage

**MODEL VIEWER, PDOK AERIAL CONTEXT, CONTROLLED EVIDENCE AND DORA: VERIFIED.**

The app can now automatically launch Rhino and complete an isolated Grasshopper
solve. The compiled desktop shell now starts/stops its own authenticated backend
and includes a native `.3dm` picker. Numeric
placement, result polling, model-grounded AI advice and printable reporting are
available. Rhino can now also generate an isolated placement-preview scene before
Grasshopper, including supported visual-only geometry, and the UI renders it with
live numeric/unit draft transforms separately from immutable calculated evidence.
The placement/viewer workflow, stable geometry summaries and controlled same-run
top/overview/facade/park captures are now implemented and hash-bound to calculations.
An attributed, locally pinned PDOK 2025 orthophoto now supplies visual site context
beneath the design and existing 3D building meshes.
Unverified north, plot and ground remain unavailable. The AI receives a bounded text
package derived from the controlled views, geometry and unchanged metrics; evidence
images remain local for human review and are not uploaded. Strict evidence-linked
response validation is implemented and mock-verified. Endpoint-specific certificate
trust remains available for private deployments. Live provider acceptance still
requires an ephemeral user credential and an exact supported model ID.
The complete desktop v1 remains in development.

### Coloured volumes and site-aware advice guard, 2026-10-14

- Replaced projected point labels in report images with deterministic design-mass
  colours and a compact legend: Volume A blue, Volume B orange and Volume C purple.
  The Grasshopper exporter writes the colours into `PH_DESIGN`, so they remain stable
  in the viewer and all four controlled captures instead of being report overlays.
- Model-evidence captures now hide shadow, UTCI and pile meshes while retaining the
  design, façades, park target, reference buildings and pinned aerial. This keeps the
  masses legible; calculated analysis layers remain available in the interactive
  viewer and metric tables.
- Capture manifests require `volume-colors-v1`, preventing a colour legend from being
  paired with older monochrome evidence. Existing runs must be analysed and captured
  again before producing the new report layout.
- Repository review found no verified tunnel alignment, depth, protection envelope,
  plot or access dataset. The AI evidence now states that absence explicitly. Until an
  authoritative constraint package is added, the prompt and server validator reject
  shifting, setting back, widening or rotating a mass and limit suggestions to tests
  that stay within the current footprint. Older advice is omitted by the new
  `site-constraints-v1` policy rather than continuing to show unsafe relocation text.
- Real `massa fase 2.3dm` acceptance passed with meter interpretation. The four 768 x
  512 captures show three distinct coloured masses without marker labels or analysis-
  mesh obstruction. Baseline Rhino numerical acceptance and stable volume-colour
  checks pass; app regression is **127 tests**, analyzer regression is **25 tests**,
  Edge/WebGL capture passes without JavaScript exceptions, and desktop Release builds
  with zero warnings/errors.
- Rebuilt and silently installed tester acceptance passes, including the installed
  payload smoke test. Unsigned artifact:
  `artifacts/ParkHaven-Setup-v0.1.0-win-x64.exe`, **65,376,804 bytes**, SHA-256
  **f9539ce7c682b4bf7dd02c41d3cffa4037b1db64f1d82848a15cb9114177805a**.
- Final A4 PDF acceptance used the real `massa fase 2` colour captures and produced
  a two-page report with the Volume A/B/C legend, no point labels, and the explicit
  unavailable tunnel/plot/access limitation. The advice text remained within the
  current footprint.

### DeepSeek, native PDF and integrity hardening, 2026-10-14

- Added an official DeepSeek compatibility profile that disables thinking and
  reasoning effort and requests JSON output. Other OpenAI-compatible endpoints retain
  the generic request shape. Grounded provider aliases are normalized without
  accepting unknown view, object or metric references.
- AI output now requires exactly three distinct prioritized design actions. Each uses
  the requested 5-10% relative sensitivity range and includes a grounded spatial
  direction, objective, conditional effect, trade-off and recalculation metrics.
  Legacy compact recommendations no longer bypass this contract.
- Provider success/error bodies and evidence JSON now have bounded reads. Endpoint
  URLs reject embedded user information, query parameters and fragments so secrets
  cannot enter persisted endpoint settings or logs. Refusal details remain bounded
  and redact the ephemeral API key.
- Evidence publication now includes the run-local weather hash. AI loading and report
  rendering require matching scene, geometry, results, weather, manifest and image
  hashes; modifying any captured image or calculated artifact makes saved advice
  ineligible for grounded display. Report screening tables appear only when every
  metric needed by the table is present.
- Native desktop PDF export uses WebView2 `PrintToPdfAsync` with an explicit Save
  dialog and A4 settings, avoiding browser print headers. The real WebView2 smoke test
  reached the native dialog from the report's `#save-pdf` control.
- Removed broad recursive installer pre-deletion of generic `backend` and
  `RhinoPlugin` directories and disabled destination-directory selection. Upgrade
  installation now overwrites only packaged paths instead of deleting an arbitrary
  user-selected tree before validation.
- Verification: **124 Python tests pass** with the known TestClient deprecation
  warning; `git diff --check` passes apart from line-ending notices; desktop Release
  build passes with zero warnings/errors; Python compilation and both JavaScript
  syntax checks pass; the isolated packaged payload smoke test passes. The rebuilt
  unsigned tester is `artifacts/ParkHaven-Setup-v0.1.0-win-x64.exe`, **65,371,658
  bytes**, SHA-256
  **66602b0956645addd9863aa8defdf94f5ddf432e0d307e3fad8ee949f994e99e**.
  Silent upgrade installation and the installed-directory payload smoke test pass.
- Remaining release limitations: packages and Rhino plug-in are not Authenticode-
  signed because no signing certificate is available; EPW redistribution approval is
  external; submitted controlled-camera metadata is structurally validated and
  hash-bound but not independently reconstructed server-side; live provider inference
  remains unclaimed without the user's ephemeral key.

### AI timeout and model compatibility, 2026-10-09

- Increased the AI provider response timeout from 120 to **180 seconds** for slower
  local vision models.
- Shortened the system instruction, requested at most three concise items per list
  and compacted the evidence JSON encoding. Removed optional `temperature`,
  `response_format` and image `detail` request fields that some OpenAI-compatible
  providers reject; evidence content and strict returned-reference validation remain.
- Added support for provider JSON returned in a Markdown JSON fence or a standard
  text content-parts list. HTTP provider errors now expose a bounded provider message
  while redacting the submitted API key. Text-only models still fail explicitly
  rather than silently dropping the required visual evidence.
- Focused AI/API/TLS regression: **36 tests pass**; full regression: **93 tests
  pass** with the known TestClient deprecation warning. The rebuilt tester installed
  successfully, its isolated payload smoke test passes, Spark TLS still reaches the
  credential boundary at HTTP 401, and the desktop remained running after startup.
- Updated installer: `artifacts/ParkHaven-Setup-v0.1.0-win-x64.exe`, 65,132,327
  bytes, SHA-256
  **82945cf13d5d1b71c6026d4103a04d4a3687a8a3d6f63ea72c8ec815f060cbd8**.
  Live model inference remains unclaimed until tested with the user's ephemeral key.
- **Visual-response compatibility follow-up:** installed use reached a valid provider
  response but rejected a visual observation because Gemma did not reproduce the
  requested field shape exactly. Validation now normalizes safe equivalents such as
  `observatie`/`tekst`, singular/plural evidence-ID fields, a missing optional
  `object_ids` list and a missing uncertainty statement. Missing uncertainty is
  recorded explicitly as not specified by the model. Unknown evidence IDs remain
  rejected. Focused AI/API/TLS regression: **37 tests pass**; full regression:
  **94 tests pass**. Rebuilt installed-payload and TLS smoke tests pass, installation
  succeeded and the desktop remained running after startup. Updated installer:
  **65,135,221 bytes**, SHA-256
  **8642eddc0e915bc307cca91473cfadfc16046a944cf56ca524b175d5ce835278**.

### Actionable AI advice and report cleanup, 2026-10-09

- Replaced free-form recommendations with exactly three prioritized, structured
  design actions. Every action must name a labelled volume, supported operation,
  camera- or volume-anchored direction, concrete test magnitude, design objective,
  hypothesized effect, trade-off, recalculation metrics and valid evidence refs.
- Added deterministic design-element derivation for up to eight principal analytical
  volumes. Stable `Volume A`, `Volume B`, etc. labels retain exact source object IDs,
  dimensions and per-camera relative screen positions without modifying source/run
  geometry or evidence images.
- `massa fase 2` acceptance uses its existing completed run: its three source Breps
  map to Volume A/B/C in south-to-north local order and to left/middle/right in the
  overview image. Heights remain the evidenced 58/56/56 m. A dedicated regression
  fixes this mapping and camera-relative distinction.
- Rebuilt the printable report around design-action cards, current metric tiles,
  human-readable evidence labels, observation uncertainty, a four-image evidence
  gallery, compact limitations and separated technical provenance. Raw UUIDs and
  internal metric tokens are no longer shown in the main report. Existing older
  advice is rendered as cleaned general advice until a new model request is made.
- Automated verification: focused AI/report/API tests pass and the full suite passes
  **98 tests** with the known TestClient deprecation warning. Live Qwen/Gemma output
  still requires the user's ephemeral API key after installation.
- Edge report acceptance with the existing `massa fase 2` evidence passes at 1280 px
  and 390 px without horizontal overflow; all four evidence figures render and the
  generated report contains no raw object UUID or metric reference tokens.
- Installed tester acceptance passes: bundle isolation and secure Spark TLS checks
  pass, installation completed successfully, and the desktop remained running after
  startup as process `19320`. Updated installer:
  `artifacts/ParkHaven-Setup-v0.1.0-win-x64.exe`, **65,143,162 bytes**, SHA-256
  **fb3a47fefda0d90db63c5598960fb7def04ddd06f06df7f34bc831c510d45231**.

### Grounded response repair and compact PDF, 2026-10-09

- Fixed the reported false rejection of concrete directions such as `naar rechts`:
  when the action already cites a valid controlled view, its human-readable view
  anchor is now added deterministically. Unknown evidence and genuinely vague
  directions remain rejected.
- Added exactly one JSON-only provider repair attempt for malformed structured
  responses. Evidence images are not resent; final failures expose only bounded
  validation details and received field names, never the API key.
- New captures frame the analytical design plus a controlled context margin instead
  of the full aerial extent. Report images project stable Volume A/B/C markers onto
  the evidenced object centres and spread labels to remain readable in side views.
- The A4 report now uses a fixed three-column metric row and two-column evidence
  gallery, Dutch date/status labels, cleaned model terminology and compact page-break
  rules. Actual `massa fase 2` Edge PDF acceptance produces a searchable **2-page**
  report with all four images, no run UUID and no browser headers when the documented
  print option is disabled.
- Verification: **100 Python tests pass**, compileall passes, `git diff --check`
  passes apart from existing line-ending notices, and the real Edge/WebGL workflow
  passes all four controlled 1200x800 captures without JavaScript exceptions.
- Private tester payload isolation and installed Spark TLS checks pass; credential-
  free `/models` reaches HTTP 401. The installed desktop remains running as process
  `23952`. Updated installer: `artifacts/ParkHaven-Setup-v0.1.0-win-x64.exe`,
  **65,149,606 bytes**, SHA-256
  **47ed7041c1cffccba3bbd194b927578a05f21f1fc47addeb1de8ac16412de684**.
- Live model inference remains unclaimed until run with the user's ephemeral API key
  and exact deployed vision model ID.

### Installed Spark TLS remediation — complete, 2026-10-09

- Root cause: development selected the ignored `config/ai-trust.local.json`, while
  the installer always packaged the tracked empty `config/ai-trust.json`. The live
  certificate and its configured leaf SHA-256 pin had not rotated and remained valid.
- The private tester build now selects the local deployment profile when present and
  includes only its referenced public certificate files. Builds and bundle checks
  reject missing files, paths outside `config/`, private-key material and invalid
  certificate stores. No API key or other credential is packaged.
- Runtime trust remains restricted to the exact HTTPS origin and pinned leaf. Normal
  certificate-chain and expiry checks remain enabled; redirects cannot cross origins.
  Runtime configuration now also rejects CA paths outside its configuration folder.
- Installed acceptance PASS: the isolated installed payload smoke test passes, and a
  credential-free request using the installed trust files reaches `/spark/v1/models`
  over verified TLS and receives HTTP 401. Installed profile/certificate hashes match
  the deployment inputs exactly. The installed desktop remained running after startup.
- Verification: **91 Python tests pass**, including CA path-escape rejection. The new
  installer is `artifacts/ParkHaven-Setup-v0.1.0-win-x64.exe`, 65,131,009 bytes,
  SHA-256 **d71693d134f95644f9953bc04a6fcbf57285f937a5c724eb4993c0da6c168056**.
- Remaining Spark acceptance requires the user's ephemeral API key and exact vision
  model ID for authenticated model listing and one evidence-grounded vision request.

### Active remediation — installed preview, massa fase 2 BVO and viewer order, 2026-10-08

- User-reported acceptance issues: the shared installed build could not create a
  3D placement preview; `../massa fase 2.3dm` did not produce BVO with the current
  runtime definition; and placement/setup controls appeared below the 3D viewer.
- **Installed-preview root cause confirmed in code:** development registration and
  backend lookup use the bare plug-in GUID registry key, while the Inno installer
  writes a braced GUID key. Package smoke tests checked file presence and HTTP
  resources but never exercised installed registry lookup, Rhino startup or scene
  creation. A development registration could also mask this defect locally.
- Preview/analyser assets are present in the packaged backend. The fix must make
  installer registration and backend discovery use one exact registry contract,
  improve installed-user errors, and add installed-path preview acceptance that
  verifies the actual installed `.rhp` and packaged analyzer paths.
- Current BVO preserves the original concept: horizontal slices at floor-height
  intervals, joined closed section curves, planar floor faces and summed area in
  square metres. The shipped GHX obtains `PH_DESIGN` through a Geometry Pipeline;
  app preparation currently accepts only visible, unlocked, valid solid Breps and
  extrusions as analytical volumes.
- `../massa fase 2.gh` and `../massa fase 2.3dm` are the user-supplied working
  reference. The next diagnostic is a controlled live run of the model plus GH
  archive inspection to identify its direct-reference input strategy and geometry
  types. Any fix must retain the current section-area concept rather than replacing
  BVO with a different metric.
- **Viewer-order cause confirmed:** DOM order places the full-width 520 px viewer
  before step 02 placement controls. JavaScript already enforces save -> preview ->
  inspect -> approve/analyse. The minimal UI correction is to move the placement
  card before the viewer and make the placement card full width; IDs and behavior
  can remain unchanged.
- Verification pending: model-specific Rhino preview/analysis, baseline numerical
  regression, source/hash preservation, installed package preview, full Python and
  browser/native workflow checks.
- **Initial live `massa fase 2` reproduction:** the production path reached
  Grasshopper and classified all three input objects as analytical Breps, then
  failed with `Grasshopper leverde geen geldige waarde voor bvo_m2`. The BVO
  component warning was `An open floor section cannot be measured.` Source and all
  isolated copies retained their hashes.
- The file declares millimetres while its raw dimensions are approximately
  `175.31 x 330.57 x 60.07` coordinates, yielding an implausible interpreted size
  of `0.175 x 0.331 x 0.060 m` with file units. A meter-interpretation run is in
  progress to isolate units from section joining; no automatic filename-specific
  unit correction will be introduced.
- **Reference graph diagnosis completed:** `massa fase 2.gh` merges and joins the
  design Breps, applies a solid union, sections that union on one shared series of
  horizontal floor planes, joins all curves per plane, creates boundary surfaces
  and sums their areas. The current embedded script instead sectioned each mass and
  failed the whole calculation on any open fragment. The implementation is being
  aligned to the reference graph while retaining current floor datum, partial-storey
  handling, unit conversion and closed-solid validation.
- A first real-model test after adding solid union still found an unclosed section.
  Archive inspection confirmed the reference `Join Curves Plus` component receives
  an explicit `1.2` join tolerance. The embedded implementation is therefore being
  tested with the same 1.2 m authored tolerance converted to Rhino document units,
  never below the document absolute tolerance.
- **Real-model BVO now completes:** exact minimum-height slicing produced 68
  coplanar edge fragments. Feeding those fragments directly to planar-boundary
  creation completed but overcounted duplicate faces. The current implementation
  retains exact floor planes where they form complete closed contours and retries
  a branching coplanar section two model tolerances above the face. With explicit
  meter interpretation, `massa fase 2.3dm` now completes at **51,867.81193063637
  m2**, sight **24.53%**, and matching cost **EUR 93,362,061.47514547**; source,
  working, run and analyser protected files retained their hashes. Numerical
  acceptance remains pending comparison to the supplied GH and baseline regression.
- **Baseline numerical regression PASS:** the real Rhino plug-in path still returns
  the exact verified baseline BVO `17024.070833234422 m2`, sight `65.12%` and cost
  `30643327.49982196`, with source/analyser hashes preserved.
- Installer registration now uses the same bare GUID key as Rhino/backend discovery.
  Packaged desktop startup supplies the exact bundled `.rhp` path to the backend;
  registry discovery rejects a stale development registration that points outside
  the active installation.
- Step 02 placement controls now precede the full-width viewer in DOM order and are
  full width themselves. Existing control IDs and JavaScript workflow remain intact.
- Focused workflow tests pass (**16**), the full Python suite passes (**90 tests**),
  desktop Release build and both JavaScript syntax checks pass. A direct plug-in
  rebuild exposed that active Rhino sessions lock the development `.rhp`; packaging
  now builds the plug-in into its isolated build directory so an unrelated open
  Rhino session cannot block or contaminate the installer payload.
- **First installed preview PASS, repeat exposed registry normalization:** the
  installed plug-in and packaged analyser produced a complete preview. On plug-in
  load Rhino removed the installer's redundant root-level `FileName` but retained
  the authoritative `PlugIn\FileName`, causing the initial strict consistency check
  to reject the second preview. Discovery now validates Rhino's nested path directly
  against the exact active installation and permits this normal Rhino rewrite.
- **Final acceptance PASS:** the corrected installer was rebuilt, silently installed
  and exercised through two consecutive real Rhino placement previews. Both used
  `AppData\Local\Programs\ParkHaven Studio\RhinoPlugin\ParkHaven.Rhino.rhp` and
  the analyser inside `backend\_internal\analyzer`; stable object evidence, all
  scene layers and protected hashes passed. The installed native desktop picker,
  Unicode import, authenticated backend/report and clean shutdown smoke also passed.
- Final regression: **90 Python tests pass** with the known TestClient deprecation
  warning; Edge/WebGL workflow passes without JavaScript exceptions; desktop and
  isolated Rhino plug-in Release builds pass with zero warnings/errors; baseline
  BVO remains exact; `massa fase 2.3dm` completes with meter interpretation.
- Silent uninstall removed the complete install directory and bare-GUID plug-in
  registry key. The same final artifact was then silently reinstalled successfully.
- Final internal tester artifact (unsigned):
  `artifacts/ParkHaven-Setup-v0.1.0-win-x64.exe`, size **65,131,002 bytes**,
  SHA-256 **b61bfba41622b97c69ebbf3fde5d062d12077bf6922925f7439ae506c02e44e8**.
- **Capture UX follow-up:** tester evidence showed a completed analysis could leave
  the viewer in placement-preview mode, making `Vier modelbeelden vastleggen`
  remain disabled while its status requested `Laatste analyse`. Run polling now
  switches a newly completed analysis to the analysis viewer automatically and
  presents an actionable capture message. Manual preview/analysis switching remains
  available.
- Capture UX verification passes in real Edge/WebGL, including four controlled
  captures and evidence upload, and all **90 Python tests** still pass. The updated
  tester was rebuilt, silently installed with close-application handling and opened
  successfully (desktop process `28044`).
- Reopening a project that has both a placement preview and a completed analysis now
  defaults to the completed analysis scene, so capture is immediately available;
  projects without completed analysis evidence still default to their preview.
- The reopened-project default and enabled capture state pass the Edge workflow.
  The final follow-up artifact was installed and opened successfully as desktop
  process `8240`.

### Active implementation — pre-analysis preview foundation, 2026-10-01

- Defined the next bounded task as the backend/Rhino foundation for placement
  preview: create an isolated `placement_preview` job from the preserved working
  copy and saved placement, reuse model preparation, export supported design,
  visual-only and reference geometry directly from Rhino, and complete without
  starting Grasshopper or publishing calculation results.
- This checkpoint will add dedicated authenticated preview status/scene/cancel
  routes and keep preview jobs separate from the analysis-run list. It deliberately
  defers live draft transforms, viewer mode controls and the move/rotate gizmo to
  the immediately following UI slice.
- Source, preserved copy and working copy must remain byte-identical. Analysis jobs
  must retain their approval/GHX requirements and completed-run scene contract.
- Initial verification scope was focused workflow/API tests, Python/JavaScript
  syntax, the full Python regression, Rhino plug-in build, job serialization and
  a live Rhino preview. All completed successfully as recorded below.
- Backend/Rhino checkpoint implemented: preview jobs snapshot the working model and
  saved placement without requiring approval or a GHX, retain explicit
  `job_type: placement_preview`, reuse unit correction/classification/context
  preparation, and branch before Grasshopper. A native exporter writes metre/Z-up
  `scene.json` with `PH_DESIGN`, `PH_VISUAL_ONLY` and the three reference layers;
  unsupported geometry is disclosed in job warnings instead of becoming analysis
  geometry.
- Dedicated authenticated start/status/cancel/scene routes are implemented. Preview
  jobs are excluded from `runs`, exposed only as the latest `placement_preview`,
  cannot be read through analysis routes, and never load `latest.json` metrics.
  Legacy jobs without `job_type` remain analyses.
- Checkpoint verification: **47 focused Python tests pass** with the known TestClient
  warning; Python compilation passes; Rhino plug-in Release build passes with zero
  warnings/errors; the real net7 serializer harness passes preview validation and
  existing warning/failure publication. The full suite passes with **73 tests**;
  both JavaScript syntax checks pass.
- **Live Dora preview PASS:** an unapproved placement using **Meters — 1 = 1 m**,
  translation `(12.5, -3, 2)` m and 30-degree Z rotation completed automatically.
  It exported 231 design objects, 2 visual-only objects and all reference layers in
  metre/Z-up space, without loading Grasshopper or creating `latest.json`. Source,
  preserved, working, preview and analyser files retained their hashes. The
  test-owned Rhino process was stopped. Evidence and reproducer:
  `docs/rhino_preview_verification.json` and `scripts/verify_rhino_preview.py`.

### Active continuation — placement-preview UI, 2026-10-01

- Resumed after the reported device crash. The backend/Rhino preview checkpoint,
  tests and live evidence are intact; no rebuild of that completed work is needed.
- Current scope: load the latest preview through its dedicated route, show
  `PH_VISUAL_ONLY`, add explicit preview/last-analysis modes and preview start/cancel
  controls, and apply live numeric/unit draft changes only to design geometry while
  reference context remains fixed.
- Implemented explicit **Plaatsingspreview** / **Laatste analyse** modes, preview
  start/status/cancel controls and a distinct `PH_VISUAL_ONLY` layer. The viewer
  applies draft X/Y/Z, Z rotation and unit interpretation as
  `new placement × inverse(exported placement)` to design and visual-only layers;
  facade/target/context matrices remain unchanged. Invalid partial numeric input
  is not presented as a valid transform.
- Draft, saved concept, approved placement and calculated-run states are labelled
  separately. Existing metrics remain tied to their run and gain an explicit warning
  while the form contains a newer draft. Camera controls still never alter placement.
- **Verification PASS:** JavaScript syntax and Python compilation pass; all **73
  Python tests pass** with the known TestClient warning. Real Edge/WebGL smoke passes
  preview/run switching, visual-only rendering, translation/rotation/unit deltas,
  fixed reference context, preview start/cancel, stale-scene clearing and existing
  analysis/report/AI gates with no JavaScript exceptions. Native Developer smoke
  also passes, including cleanup. The initial app-venv invocation could not import
  optional Playwright; rerunning with the documented analyser venv passed.
- No new live Rhino solve was needed because this slice did not change the already
  live-verified preview exporter or preparation path.

### Active implementation — constrained placement gizmo, 2026-10-01

- Defined the next slice as an in-app gizmo without adding a CDN/runtime dependency
  or modifying the analyser: constrained XY translation, Z-axis rotation, model-
  origin/design-center pivot selection, restore-saved placement and snap of the
  selected reference point to viewer world `(0,0)`.
- World `(0,0)` is a coordinate aid only and must remain explicitly labelled as not
  being a verified legal plot point, north reference or survey control.
- Gizmo actions will update the existing numeric fields as an unsaved draft. They
  must not save automatically, move context/camera, alter old metrics, or bypass the
  existing explicit preview/analysis workflow.
- Implemented dependency-free Three.js handles for constrained X, Y and XY movement
  plus Z rotation. Orbit controls are suspended only during an active gizmo drag;
  camera movement, reference layers and calculated evidence remain unchanged.
- The user can pivot at the model origin or design center, restore the last saved
  placement, or move the selected reference point to viewer world `(0,0)`. The UI
  explicitly says this origin is not a verified plot/survey point. Design-center
  rotation adjusts X/Y so the chosen center remains fixed.
- Gizmo output is rounded to the form's 0.1 m/degree step, clears approval, updates
  the existing numeric fields and remains unsaved until the existing placement form
  is submitted. No alternate persistence or Rhino transform contract was added.
- **Verification PASS:** real Edge pointer drags pass for constrained translation
  and rotation; center snap/reset, numeric synchronization, explicit API save,
  fixed context, preview/run switching and existing gates pass without JavaScript
  exceptions. All **73 Python tests**, Python/JavaScript compilation and native
  Developer/WebView2 smoke pass. No Rhino solve was needed because preparation,
  export and the already live-verified numeric placement contract were unchanged.

### Active implementation — deterministic spatial checks, 2026-10-01

- Context provenance audit: runtime scenes contain the metre/Z-up analysis layers
  `PH_FACADES`, `PH_TARGET` and `REFERENCE_CONTEXT`, tied to the reference-model
  SHA-256 in each preview/run. They do not contain a legal plot, approved ground
  datum or versioned north transform.
- The analyser's `docs/GEOREFERENCE.md` records a strong map-derived RD New fit and
  approximate north, but explicitly calls it provisional and not a survey control.
  Hidden Forma site limits/property boundaries/terrain listed by the source audit
  are not exported into the desktop scene and cannot support runtime validation.
- Current scope: report transformed design extents, deterministic scale thresholds,
  relationship to **viewer world Z=0**, and XY overlap/distance against the available
  reference-layer envelope. The UI must state that these are not legal plot, ground
  or north checks.
- Added a responsive deterministic-check panel. It reports exact transformed XYZ
  extents/dimensions, warns below 1 m or above 500 m, classifies the lower edge
  against viewer world Z=0 with 0.05 m tolerance, and reports XY overlap/distance
  against the combined available reference-layer envelope.
- Every result names its evidence boundary: world Z=0 is not approved ground and
  reference-envelope overlap is not a plot test. The panel shows the job's context
  hash when available and keeps north/plot/maaiveld explicitly unapproved.
- Added `docs/CONTEXT_PROVENANCE.md` documenting runtime layers, the provisional
  georeference boundary, unavailable hidden source geometry and allowed checks.
- **Verification PASS:** real Edge fixtures cover correct scale/reference overlap,
  below and above world Z=0, a >900 m offset, wrong-small unit interpretation and
  context-hash display while retaining gizmo/evidence gates and no JS exceptions.
  All **73 Python tests**, Python/JavaScript compilation and native WebView2 smoke
  pass. No Rhino solve was needed because scene generation did not change.

### Active implementation — stable geometry evidence, 2026-10-01

- Defined the next bounded contract: preserve source Rhino object UUIDs through
  in-memory preparation; emit optional per-object mesh ranges in preview scene
  layers; and write a separate versioned `geometry-summary.json` for preview and
  analysis jobs.
- Summary objects will cover design and visual-only classifications with stable ID,
  source UUID, geometry type, metre bounds/dimensions/height and mesh counts. The
  package will include source/input/context hashes and the immutable job placement.
- Metadata is bounded to 5,000 summarized objects with an explicit omitted count;
  mesh export remains unchanged. Historical schema-1 scenes without optional object
  mappings must remain valid and render identically.
- Source UUIDs are retained as `source:<uuid>` through in-memory scaling/placement
  and classification. Preview layer arrays remain schema 1 and gain optional object
  ranges (`vertex_start/count`, `triangle_start/count`), so historical scenes and
  the existing viewer remain compatible.
- Both preview and analysis jobs now write `geometry-summary.json` with run/project,
  source/input/context hashes, placement, classification, geometry type, metre
  bounds/dimensions/height, mesh counts and a deterministic object-list hash. The
  complete file has its own hash and is intentionally run-specific.
- **Repeated live Dora preview PASS:** two isolated previews exported the same 233
  unique source IDs, 231 analysis volumes, 2 visual-only objects, bounds and mesh
  ranges. Their deterministic object-list hashes match while file hashes differ by
  run provenance. Protected source/working/reference hashes remain unchanged.
  Evidence: `docs/rhino_preview_verification.json`.
- **Live baseline analysis PASS:** the analysis produced a run-bound four-object
  geometry summary and unchanged BVO **17,024.070833234422 m2**, visibility
  **65.12%** and cost **EUR 30,643,327.49982196**. Evidence:
  `docs/rhino_plugin_verification.json`.
- Plug-in Release build passes with zero warnings/errors; serializer passes with its
  known net7 support warning. All **73 Python tests**, Python/JavaScript compilation,
  Edge workflow and native WebView2 smoke pass. A longer Edge run exposed and fixed
  a test mock that returned another project's active run during baseline polling.

### Active implementation — controlled model-view evidence, 2026-10-01

- Defined the next capture contract for a selected completed analysis run: four
  fixed **1200 × 800 PNG** views with stable IDs `top`, `overview`, `facade-side`
  and `park-side`. Captures use controlled cameras, fixed visible layers and the
  real Three.js scene; they are not AI-generated images.
- `facade-side` and `park-side` camera directions must derive from the loaded
  `PH_FACADES` and `PH_TARGET` geometry respectively. Missing reference geometry
  fails the set instead of silently substituting an unrelated view.
- The backend will validate PNG signatures/dimensions and bounded payload sizes,
  then compute image, scene and geometry-summary hashes server-side. A versioned
  `view-evidence.json` will bind camera metadata, layers, run/project, source/input/
  context hashes and immutable run placement. Partial/stale sets must not publish.
- Added an explicit completed-run capture action. An offscreen local Three.js
  renderer creates fixed 1200 × 800 views with all non-empty run layers visible;
  gizmo and user camera/layer state are excluded and restored after capture.
- Top and overview use fixed camera rules. Facade-side and park-side derive their
  directions from actual `PH_FACADES` and `PH_TARGET` centers; missing or unusable
  references fail the complete set.
- Added an authenticated publication endpoint with strict four-ID, perspective,
  camera, layer, PNG chunk/CRC, exact dimensions, 5 MB per-image and 16 MB total
  validation. Scene and geometry hashes supplied by the loaded viewer must still
  match server files. Geometry-summary run/project/source/context/placement fields
  are revalidated server-side.
- Publication writes images into a capture-ID directory and atomically publishes
  `view-evidence.json` last. The manifest includes image/camera/layer metadata,
  source/input/context, scene, geometry-summary, metrics and GH-definition hashes,
  immutable placement, and explicit unverified/unavailable north/plot/ground status.
  Invalid, duplicate, partial, stale and oversized sets cannot replace valid evidence.
- **Real Edge/WebGL PASS:** fixture acceptance inspects four outgoing PNG data URLs,
  exact dimensions/IDs, distinct facade/park cameras and evidence upload with no JS
  exceptions. **Live baseline PASS:** the actual four-layer Rhino scene produced four
  distinct PNGs (45–68 KB), controlled cameras and a validated same-run manifest.
  Evidence: `docs/view_evidence_verification.json`; reproducer:
  `scripts/verify_view_evidence.py`.
- All **76 Python tests**, Python/JavaScript compilation, full Edge workflow and
  native Developer/WebView2 smoke pass. No additional Rhino solve was required;
  capture used the latest verified baseline run.

### Active implementation — model-grounded multimodal AI, 2026-10-02

- Replaced the metrics-only request with a required same-run evidence loader. Every
  request revalidates analysis status, scene/geometry/results/definition/source/input/
  context/placement provenance, all four image hashes and byte limits, bounded
  geometry and stable source-derived object IDs immediately before transmission.
- The OpenAI-compatible user content now contains unchanged Grasshopper metrics,
  bounded geometry/run metadata and four labelled `image_url` data parts in stable
  `top`, `overview`, `facade-side`, `park-side` order. No text-only fallback can
  claim visual inspection.
- Added a strict Dutch response contract separating calculation evidence, visual
  observations with uncertainty, recommendations and limitations. Metric fields,
  view IDs, object IDs and recommendation evidence references are rejected unless
  they exist in the supplied package. Provider/model and evidence hashes are stored,
  while the ephemeral API key is not returned or persisted.
- The AI action remains disabled until controlled views exist. Printable reports
  render the structured evidence references only while their view manifest hash is
  current; stale or legacy non-visual advice is disclosed and suppressed.
- **Verification PASS:** **84 Python tests** pass with the known TestClient warning;
  Python and JavaScript compilation pass. Real Edge/WebGL acceptance verifies the
  capture-to-AI gate, and native Developer/WebView2 smoke passes. Mock providers
  verify four labelled image parts, malformed/unknown metric/view/object/reference
  rejection, same-run evidence loading, image tamper rejection and pinned TLS.
- **Live provider boundary:** authenticated Spark model listing, image-input support,
  structured JSON support and actual Dutch vision advice remain unverified. No API
  key or exact model ID was supplied, so this checkpoint makes no live vision claim.

### Active implementation — PDOK aerial context, 2026-10-02

- Added a reproducible 600 x 600 m clip from PDOK layer `2025_orthoHR` in RD New,
  stored as a 2500 x 2500 local JPEG. `site-context/manifest.json` pins its image
  hash, source, attribution, RD extent, four local corners and provisional alignment.
- The backend validates path containment, JPEG structure/dimensions, image hash,
  source metadata and alignment status before serving the manifest or image through
  authenticated same-origin routes. No runtime WMS, CDN, token or external tile
  dependency was added.
- Three.js renders `PDOK_AERIAL` as a separate textured plane at visual Z=-0.15 m,
  beneath the fixed 3D reference buildings. Users can toggle it and adjust opacity;
  source attribution and the non-survey/non-plot/non-ground boundary remain visible.
  Design transforms, Rhino preparation, Grasshopper and deterministic checks do not
  consume the aerial.
- Controlled captures now force the aerial visible and bind its context-manifest and
  image hashes. AI evidence includes the source/alignment metadata. Captures made
  before this package are intentionally stale and must be recreated.
- **Verification PASS:** **89 Python tests** pass with the known TestClient warning;
  Python/JavaScript compilation, real Edge/WebGL and native Developer/WebView2 smoke
  pass. A fresh live baseline capture visibly aligns Parkhaven, harbour, park, design
  and existing 3D context in all four images; image sizes are 216-441 KB. Evidence:
  `docs/view_evidence_verification.json`.
- Accuracy remains bounded by the documented provisional building-aligned transform:
  this is useful visual context, not approved grid north, legal plot, survey control
  or maaiveld. A true 3D aerial still requires a selected licensed terrain or
  photogrammetry source, vertical datum, tiling/LOD and separate acceptance.

### Latest handoff summary

| Area | Current verified state | Remaining work |
|---|---|---|
| Desktop/backend | Native picker, authenticated owned backend, shutdown/retry and Developer diagnostics pass native acceptance | Bundled Python/installer, retention and hard-crash recovery |
| Rhino calculations | Automatic baseline and corrected Dora runs pass; unit-equivalence fixtures pass with nonzero placement | Broader geometry/version coverage and interactive viewer-to-Rhino round trips |
| Dora units | Select **Meters — 1 = 1 m**, save approved placement, start a new run: **30,460.40 m2**, **61.4%**, **EUR 54,828,722.09** | User retest in the restarted app; historical run results remain unchanged |
| 3D viewer/orientation | Completed-run/preview modes, gizmo, checks, 3D reference buildings and attributed PDOK 2025 aerial pass with explicit evidence boundaries | Verified north/plot/ground controls only when approved source data exists; optional licensed 3D terrain/aerial package |
| AI model understanding | Same-run geometry, metrics and four labelled images are sent; returned metric/view/object references are schema-validated | Live acceptance with the user's exact vision model and credentials |
| Spark connection | Endpoint-specific private-certificate verification works; credential-free `/models` returns HTTP 401 | Authenticated access, actual vision/JSON capability checks and model-grounded advice acceptance |
| Quality checks | **89 Python tests pass**; compilation, Edge/native, plug-in/serializer, repeated Dora IDs, baseline metrics, aerial-backed live view evidence and mocked multimodal checks pass | Live provider checks |

Restart the desktop/backend after the latest updates. API keys belong only in
the app's password field; none is needed for the credential-free TLS check. Spark
advice can use an existing completed run, so TLS testing does not require another
Rhino solve. Use a corrected Dora run when requesting advice about that design.

### Scope revision — viewer, orientation and AI model evidence, 2026-09-30

- **User instruction for this stage: update `plan.md` first and prepare next steps
  here; build nothing yet.** Only those two documentation files are changed by
  this revision. No application code, tests, endpoints or UI features are added.
- Conceptual AI renders, a separate image-generation endpoint, generated render
  artifacts and that requirement in the v1 completion criteria have been removed
  from the active plan. Real model captures for AI/reporting remain in scope.
- Verified the current advice path in `app/main.py` and `app/ai.py`: the endpoint
  passes `job["results"]` and `design_goal`; the model receives these as text.
  **It does not currently see the 3D model.** Neither `.3dm`, meshes, `scene.json`,
  model images, geometry summaries nor placement/orientation data are sent.
  Prompt wording about visual assumptions does not supply any visual evidence.
- The planned AI change requires a same-run evidence package: deterministic
  geometry/placement/unit summaries plus actual top/perspective/facade/park views.
  Use a verified vision-capable model and reference supplied object/view IDs in
  advice. A text-only fallback must be explicitly labelled as limited and cannot
  count as visual-model acceptance.
- Viewer/orientation is first: show the actual design relative to reference
  facades, park and context, with axes, scale, dimensions, fixed views and verified
  north/plot information when available. Camera orbit is separate from changing
  the design transform. Provisional site alignment remains explicitly provisional.
- The initial viewer reads completed runs. A subsequent preview-export path is
  required to inspect an import and its placement **before** a full GH calculation,
  including supported visual-only geometry. Current scene export cannot be assumed
  to contain every imported object or stable per-object IDs.
- The detailed roadmap and acceptance criteria are in plan phases **5, 9 and 10**;
  their implementation order is viewer/orientation → placement preview → real
  model evidence → model-grounded AI. The pending work items below are the handoff.
- Existing **66-test** results remain the last verified application checkpoint.
  This documentation-only revision introduces no new implementation/test claims.

### Read-only completed-run viewer — implemented and verified, 2026-09-30

- Completed the first approved viewer slice. Scope is deliberately bounded to
  immutable `scene.json` evidence from the currently selected **completed** run.
  Placement editing, import preview, north/plot claims and AI image input are not
  part of this step.
- Reusing the analyser's locally vendored Three.js 0.180.0 modules through an
  authenticated same-origin, allowlisted static route; no CDN/runtime download.
- Planned acceptance for this slice: strict metres/Z-up scene validation, layer
  controls, orbit/pan/zoom, fit/reset and fixed orientation views, XYZ/grid/scale
  cues, run/unit/placement metadata, responsive layout, explicit empty/error/WebGL
  states, and cancellation/disposal so project switching cannot show stale geometry.
- Implemented the first slice in `app/static/viewer.js` and the workflow UI. It
  strictly validates scene schema 1 / metres / Z-up, renders the four known layers,
  adds local orbit/pan/zoom, design/all fit, reset and top/front/side controls, a
  metre grid/XYZ cues, dimensions and saved placement metadata. North/plot remain
  explicitly unverified; camera actions never persist a design transform.
- Viewer loads are run/project keyed and abortable. Selection changes clear and
  dispose old mesh/edge/material GPU resources before another scene can appear.
  Running/failed/empty states cannot retain previous project geometry.
- Backend now serves run-local scenes only after `completed`, with `no-store`.
  Viewer code and locally vendored Three.js modules are covered by the desktop's
  existing same-origin session authentication; no CDN or JS-held token is used.
- **Verification:** 70 Python tests pass (one existing TestClient
  deprecation warning), JavaScript syntax and Python compilation pass. Tests now
  cover scene completion gating, missing evidence, exact bytes/media/no-store and
  authenticated viewer/module routes.
- **Real Edge/WebGL PASS:** rendered a completed run, counted scene triangles,
  displayed physical dimensions, exercised top-view and layer controls, then
  switched projects and verified the old scene was cleared. Existing placement,
  unit, start/cancel, report/advice gates still pass with no JavaScript exceptions.
- **Native WPF/WebView2 smoke PASS:** the updated web UI/modules did not regress
  the Developer tab, backend timeout/exit distinction, redacted logs or retry.
  WebView2 teardown also exposed WinError 145 (`directory not empty`) as another
  transient profile-release condition; bounded cleanup now retries WinError 32
  and 145 for up to 15 seconds and still fails if either persists.
- No Rhino solve was needed: this viewer consumes immutable, already verified
  run-local scene evidence. It does not claim import preview, editable placement,
  geographic north, legal plot boundary or AI model vision.

### Spark private HTTPS certificate — configured and verified, 2026-09-30

- A user-approved private-certificate AI server was verified. Its certificate name
  did not match the endpoint address, so both issuer trust and exact certificate
  identity needed handling. Deployment identity is now retained only in ignored
  local configuration, not in the source-repository candidate.
- Added `app/ai_tls.py` and endpoint-scoped local trust profiles. The tracked
  configuration is empty and `config/ai-trust.example.json` contains placeholders.
- Configured requests still require a valid certificate chain and dates. An exact
  leaf-certificate pin replaces hostname matching only for that configured origin;
  it is checked during connection setup before HTTP headers/API keys are sent.
  Other endpoints retain normal system trust and hostname checks. Cross-origin
  redirects are blocked, including HTTPS-to-HTTP downgrade.
- **Live check PASS:** `scripts/verify_ai_tls.py` reaches `/spark/v1/models` over
  verified TLS and receives HTTP **401** without credentials. No key/project data
  was sent. This resolves the reported certificate failure; authenticated model
  listing, permissions, JSON output and actual inference still need the user's
  server API key/model ID and have not been claimed as verified.
- **66 Python tests pass**, including real local-TLS tests for success, changed
  fingerprints, expired certificates, host/port/protocol scope, invalid profiles
  and redirect rejection. Added `trustme` only to development requirements.
- Restart ParkHaven to load the updated Python backend. Then use the supplied base
  URL, server API key and exact model ID with an existing completed run. No Rhino
  recalculation is needed for the certificate change. Setup/rotation details:
  `docs/AI_TLS.md`. Override trust-file location with `PARKHAVEN_AI_TRUST_CONFIG`.

### Dora BVO / visibility / costs — units corrected, 2026-09-30

- Checked the millimetre hypothesis first, as requested. The file declares
  **Millimeters**, but its numerical coordinates describe metre-sized buildings:
  a height of 21 was being interpreted as 0.021 m. The raw overall dimensions are
  approximately **142.74 × 252.46 × 43.06** coordinate units. The GH components
  already respect document units; changing only the reported BVO would not fix
  either the floor-plane spacing or the design's position relative to sight rays.
- Added a persisted **Modeleenheid** selector to placement: file units (default),
  metres, millimetres, or centimetres. **For Dora choose Meters — 1 = 1 m**, approve
  and save the placement, then start a new analysis. Restart the desktop/backend
  after this code update so it loads the new API field and UI.
- The correction is part of the immutable per-run placement snapshot. It scales
  design/visual geometry and absolute tolerance in the run's in-memory document,
  before rotation and translation. Translation remains in physical metres;
  verified site context still converts using the document's declared units.
  For Dora this means factor **1000** in the millimetre document. Source, preserved
  copy, project working copy and run input file remain byte-for-byte unchanged.
- Genuine millimetre models retain factor **1** with the default file-unit option.
  No filename-specific rule or automatic unit guess was introduced. A sub-metre
  overall design now gets an explicit unit-check warning. The UI shows the actual
  run's declared/interpreted units, applied factor, physical dimensions and warnings.
- Unsaved placement/unit edits disable starting a run until saved. Selection
  survives reopening a project; older API callers omitting the field retain an
  existing correction. Older projects without the field use file units.
- **Live Dora PASS:** BVO **30,460.40116279473 m2**, visibility **61.4%**, indicative
  cost **EUR 54,828,722.09303051** at EUR 1,800/m2. This is the actual Grasshopper
  output, close to the user's approximate 31,000 m2 expectation; no output metric
  is overridden. See `docs/rhino_dora_units_verification.json`. The former 0.00424 m2 /
  100% / EUR 7.64 result in `rhino_dora_verification.json` is retained as historical
  pre-correction evidence, not the current accepted result.
- **Known-size unit equivalence PASS:** a 10 × 20 × 9 m box produces **600 m2**,
  **98.26%** visibility and **EUR 1,080,000** in metre, true-mm and corrected-mm
  forms. All scene bounds agree within 0.1 mm after translation (12.5, -3, 2) m
  and 30° rotation. Evidence: `docs/rhino_unit_equivalence.json`;
  reproducer: `scripts/verify_rhino_unit_equivalence.py` (optional `rhino3dm`).
  Test-only rhino3dm 8.35.0 was installed under `%TEMP%\opencode\rhino3dm-tools`,
  not added to application dependencies.
- Original numerical/scene baseline recheck: **PASS**. Plug-in Release build:
  **PASS, zero warnings/errors**. Python suite: **58 passed**. Real Edge unit
  selection/save/reopen/unsaved-edit smoke: **PASS**. The registered plug-in was
  rebuilt after the user closed the Rhino sessions holding its file lock.

### Dora preparation stall — fixed, 2026-09-30

- Reproduced with `../test-ui-dora.3dm` (6,297,013 bytes, SHA-256
  `078cf8bcdc18b19d99e644abffa9ee6e14077916b8ed42f097a9e1ba112b656c`).
  Previous user runs remained in preparation until cancellation, including one
  after over nine minutes. Investigation used isolated copies and test-owned Rhino.
- **Root cause was failed status serialization, not expensive geometry work.**
  Dora contains 233 Breps: 231 analytical objects and 2 visual-only objects.
  Appending the visual-only warning through `JsonArray.Add<T>` in the net7-built
  plug-in / Rhino .NET 8 host produced a `JsonValueCustomized<T>`. Saving it raised
  `JsonSerializerOptions instance must specify a TypeInfoResolver setting before
  being marked as read-only.` The exception handler retried serialization of the
  same warning and failed again, leaving the last on-disk status `preparing_model`.
  The earlier baseline has no classification warnings, so it did not expose this.
- Fixed `AnalysisJob` serialization with explicit `DefaultJsonTypeInfoResolver`
  metadata and explicit `JsonValue.Create` warning nodes in preparation and GH
  solving. Original exceptions now also go to run-local `runner-error.log`, with
  guarded handling if status publication itself fails.
- Added real substeps, throttled object progress, step timings, unit/type counts
  and stable phase-start timestamps. Progress/timings appear in the native Developer
  tab; unit/type counts are retained in `job.json`. The workspace status also shows
  the current substep. Grasshopper startup is now
  explicitly visible instead of looking like unchanging geometry preparation.
- Frequent diagnostic polling exposed transient Windows sharing conflicts around
  atomic job replacement. Added bounded publication/read retries and a regression
  test; job publication remains atomic. Unsupported non-volume geometry no longer
  undergoes unnecessary analytical validity checks.
- **Live Dora acceptance PASS:** complete results and scene in **37.26 seconds**,
  approximately **0.68 seconds preparation**, **18.18 seconds GH startup** and
  **8.73 seconds solving** (remaining time is Rhino startup/polling). The two-object
  warning is retained. Source, preserved copy, working copy, run snapshot and
  analyser inputs/baseline outputs all retain their SHA-256 hashes.
- **Live numerical baseline recheck PASS** after the fix: all three metrics and
  all scene-layer counts/bounds still match. Evidence:
  `docs/rhino_dora_before.json`, `docs/rhino_dora_verification.json`, and refreshed
  `docs/rhino_plugin_verification.json`. Reproducer: `scripts/verify_rhino_import.py`.
- **Historical input/result issue (resolved by the units checkpoint above):** Dora declares **Millimeters**, and
  this run outputs BVO **0.004242843546617502 m2** and indicative cost **EUR 7.64**.
  This verifies execution, not physical plausibility or correct design placement.
  These initial metrics were not accepted. The later units checkpoint identifies
  and corrects the coordinate interpretation without changing the source.
- Rebuilt the registered Rhino plug-in and normal desktop Release executable.
  The user authorized normal closure of their open desktop to release the build
  lock. Reopen the desktop and start a **new analysis** to test the fix; old
  cancelled runs are historical evidence and are not rewritten.

### Active implementation — 2026-09-29

- Read the desktop plan at `../ParkHaven_Analyzer_App_v0.2/docs/plan.md`.
- Installed a portable .NET **8.0.425 SDK** under
  `%TEMP%\opencode\dotnet-sdk` for local compilation (system PATH unchanged).
- Implemented and verified the native C# `ParkHavenAnalyze` command and
  startup/idle dispatch, replacing the skipped `/runscript` dependency.

#### C# implementation checkpoint

- Added `rhino-plugin/` with `ParkHavenAnalyze`, startup idle dispatch restricted
  to the job's document, run locking, native RhinoCommon model preparation and
  Grasshopper loading/solving. Reference layers are excluded from design
  classification, and their units are converted to match the design document.
- Each run now snapshots its own `.3dm` and GHX, records input/definition/context
  hashes and targets, and launches Rhino directly with `/netcore`.
- Added per-user plug-in registration, backend process monitoring, startup/solve
  timeouts and a cancellation endpoint. Job status is published before launch to
  avoid overwriting early plug-in results.
- .NET build: **PASS, zero warnings/errors**. Existing Python suite: **16 passed**.
- Live Rhino baseline acceptance: **PASS** on Rhino/Grasshopper
  `8.27.26019.16021`, .NET runtime `8.0.31`. The app launched Rhino and the
  plug-in solved automatically in approximately 28 seconds including startup.
- Reproduced BVO **17024.070833234422 m2**, visibility **65.12%**, and indicative
  cost **EUR 30643327.49982196**, with four design masses, 34 facade objects,
  one target and 537 reference objects. All four scene layers matched baseline
  vertex/triangle counts and bounds. No Grasshopper warnings were reported.
- SHA-256 checks confirm the source, preserved copy, working copy, run model,
  analyser model/definitions and baseline JSON files remained unchanged.
- Evidence: `docs/rhino_plugin_verification.json`. Reproducible acceptance:
  `scripts/verify_rhino_plugin.py`. The test-owned Rhino process was stopped.
- Startup registration initially failed because the root registry `FileName`
  value was absent; adding it fixed first-use registration and startup loading.

#### Workflow verification checkpoint

- Added Dutch cancellation/status controls, disabled duplicate starts while a run
  is active, and cleared previous project evidence when switching projects.
- Added regression tests for isolated input snapshots, provenance, fast plug-in
  completion races, duplicate/concurrent launch rejection, process creation
  failures, Rhino crashes, startup/solve timeouts and owned-process cancellation.
- Added a real Edge smoke test with mocked analysis APIs. Its first execution
  found CSS overriding the metrics panel's `hidden` attribute; fixed the hidden
  rule so stale metrics cannot remain visible. **Edge recheck PASS**: project
  switching, evidence clearing, start/cancel controls, report/advice gating and
  no JavaScript exceptions.
- Completed this milestone's checks: **27 Python tests pass**, JavaScript syntax
  and Python compilation pass, C# build passes, and live Rhino baseline acceptance
  passes. Build/setup/manual fallback and repeatable verification are documented
  in `docs/RHINO_PLUGIN.md`; the README and start guide are current.

### Small task completed: native design selection

- Implemented a Dutch `Bladeren...` button in the desktop import form, with a
  WebView2 message bridge to the Windows `.3dm` file dialog. Browser mode retains
  typed paths. Selecting a file fills the form; import remains a separate action.
- Dialog requests are correlated, cancellation preserves the current path, and
  duplicate selection/submission is disabled while the dialog is active.
- Restricted desktop navigation/message handling to the configured loopback app
  origin and moved the WebView2 profile to writable per-user storage.
- Desktop Release build: **PASS, zero warnings/errors**.
- `tests/desktop_picker_smoke.py`: **PASS** in the actual WPF/WebView2 shell with
  a real Windows file dialog and isolated live FastAPI backend. Verified cancel
  preserves the current path, selection handles spaces/Unicode/apostrophes,
  selection alone does not import, explicit project creation succeeds, and
  source/preserved/working files have identical SHA-256 hashes.
- The native test automates only visible dialogs owned by its own shell process;
  test-owned backend/shell processes and temporary data are cleaned up.
- Browser workflow smoke and JavaScript syntax: **PASS**. Backend regression
  suite: **27 passed** in 3.18 seconds.
- Desktop build/launch instructions are in `desktop/README.md`. The subsequent
  lifecycle milestone below removes the separate-backend startup requirement.

### Desktop backend lifecycle — completed, 2026-09-30

- Implemented a shell-owned backend with an OS-assigned loopback port, private
  stdin configuration/shutdown control, authenticated readiness, and per-session
  logs. The session secret stays out of command lines, URLs and project files.
- Added authentication for all desktop HTTP routes (including HTML, assets and
  reports), plus host/origin checks. Browser development mode remains explicit.
- Added normal-close and parent-disconnect shutdown, owned Rhino cleanup,
  startup status/retry UI and authenticated report windows.
- Implementation checkpoint: **46 Python tests passed** including real backend
  subprocess startup/shutdown, authentication boundaries and owned Rhino cleanup.
  Desktop build: **PASS, zero warnings/errors**.
- Actual desktop acceptance now passes: shell-owned random-port backend, native
  picker/import, authenticated report window, and normal window-close shutdown.
  Report windows are created after returning from the WebView2 callback to avoid
  nested native UI lifecycle issues.
- `tests/desktop_lifecycle_smoke.py`: **PASS** in the real desktop shell for
  missing Python, early backend exit, retry after repairing startup, backend
  crash/retry, 30-second readiness timeout, close during startup, two independent
  sessions and parent-crash cleanup. An early-exit notification race was fixed
  so it does not overwrite a useful startup failure with a generic disconnect.
- `tests/desktop_picker_smoke.py`: **PASS** for owned/authenticated startup,
  native file selection/import, source preservation, authenticated report popup
  and normal-close backend shutdown. Report content in this test is explicitly
  seeded mock data; the previous live Rhino baseline evidence remains separate.
- Python compilation: **PASS**. Test-owned shell/backend processes are cleaned up.
- Updated desktop README, app README and start/Rhino guides. Desktop launch now
  requires only the executable after setup/build; installer packaging is pending.

### Developer tab — completed, 2026-09-30

- Native `Developer` tab stays available when the web backend fails. It shows
  launcher/backend process state, timed HTTP checks, last successful response,
  recent run phases/substeps/timings/errors/warnings and retained, redacted logs.
- `/api/developer/status` is authenticated in desktop mode, read-only, no-store,
  bounded to recent runs and explicit redacted fields. Corrupt records do not take
  down the panel. Phase age is separate from throttled progress updates.
- Finished the interrupted native smoke task: WebView2 profile release is
  asynchronous after shell shutdown. Test cleanup now retries transient sharing
  errors for up to 15 seconds, still failing if the lock persists. PASS is printed
  only after cleanup completes.
- `tests/desktop_developer_smoke.py`: **PASS with successful process exit and
  cleanup**. Verified live substeps/timings/errors, preserved unsaved form input
  across tab changes, a suspended backend versus an exited backend, redacted
  native/disk logs, retained crash diagnostics and successful retry.

## Environment findings

- .NET 8 desktop runtime is installed.
- A portable .NET 8.0.425 SDK is now available at
  `%TEMP%\opencode\dotnet-sdk\dotnet.exe`; it is not on system PATH.
- Both the Rhino plug-in and WebView2 shell build and run successfully locally.
- Python 3.14.7 and the existing analyser development environment are available
  for verifying the initial backend slice.

## Completed

- Read the source `README.md`, `docs/PROGRESS.md`, build guide, georeference and
  desktop product plan.
- Confirmed the existing analyser has local FastAPI/Three.js interfaces suitable
  for staged reuse.
- Confirmed the source worktree already contains user changes; they are not being
  modified or reverted.
- Created an independent `ParkHaven_App_v0.1` application rather than copying or
  changing the verified analyser.
- Added a versioned project manifest and isolated workspace under the configured
  projects root.
- Added safe `.3dm` import that:
  - validates the local source path, extension and non-empty file;
  - calculates SHA-256 before copying;
  - preserves `source/original-design.3dm`;
  - creates `working/parkhaven-design.3dm`;
  - verifies both copies and rechecks the source;
  - removes partial workspaces after a failed import.
- Added initial `placement.json`, `repairs.json` and `targets.json` contracts.
- Added UUID validation so project API paths cannot escape the project root.
- Added a Dutch responsive project creation/listing UI with native `.3dm`
  selection in the desktop shell and typed paths in the browser.
- Added FastAPI health, project creation, project listing and project detail
  endpoints with no-store responses.
- Added setup/start commands and dependency declarations.
- Added a compiled .NET 8 WPF/WebView2 shell with owned backend startup/shutdown,
  random authenticated loopback ports, readiness checks, logs and retry controls.
- Added project continuation UI instead of stopping after import.
- Added validated, persisted X/Y/Z translation and Z-axis rotation with an
  approval gate before analysis.
- Added one isolated run directory and copied GHX per analysis so Grasshopper
  outputs cannot overwrite another project.
- Added a compiled Rhino plug-in that:
  - classify closed Breps/extrusions as `PH_DESIGN`;
  - apply the approved transform in memory;
  - replace fixed facade, target and reference layers from the verified model;
  - load and solve the run-local GHX;
  - publish run-local `latest.json` and `scene.json` without saving the source.
- Added direct visible Rhino launch and the `ParkHavenAnalyze` manual fallback.
  The legacy Python entry point now delegates to the plug-in command.
- Added run status/result APIs and UI polling.
- Added an ephemeral OpenAI-compatible Dutch review client. API keys are not
  persisted; external plain HTTP endpoints are rejected.
- Added explicit per-project coordinate-unit interpretation, per-run unit/factor/
  tolerance provenance and UI protection against starting with unsaved placement.
- Added native Developer diagnostics with retained redacted logs and real Rhino
  substep timings, including useful failure evidence after backend loss.
- Added origin-scoped private-certificate trust for the supplied Spark server,
  exact certificate pinning before API-key transmission and redirect restrictions.
- Added a printable Dutch HTML report with Save-as-PDF workflow. It separates
  Grasshopper evidence from AI inference and omits unavailable future metrics.
- Added `docs/START_TEST_GUIDE.md` with setup, workflow, tests and troubleshooting.

## Verification

Latest desktop checks on 2026-09-30; earlier Rhino evidence retained:

- App-local `.venv` used for the backend regression suite. The existing analyser
  environment supplies only the already-installed optional Playwright browser
  test dependency.
- `python -m pytest -q`: **66 passed**, including private TLS certificate scoping,
  pin/date checks and redirects, plus unit-selection validation,
  persistence, legacy-client compatibility, per-run unit snapshots, diagnostic
  authentication/redaction/bounds and transient Windows read locks.
- `tests/rhino-job-serialization/JobSerialization.csproj`: **PASS** using the real
  net7-compiled `AnalysisJob` in the .NET 8 host: original generic-warning path,
  failure publication with warnings still present, timing and stable phase age.
  The console harness emits the SDK's net7 end-of-support warning; Rhino's target
  framework has not been changed by this fix.
- `python -m compileall -q app tests scripts`: **PASS**.
- `node --check app\static\app.js`: **PASS**.
- `tests/browser_workflow_smoke.py` in real headless Edge: **PASS** with mocked
  analysis endpoints, including unit selection/save/reopen and unsaved-edit
  protection. This browser check is separate from the real Rhino solves.
- Tests cover source preservation, verified copies, manifests, invalid/missing/
  empty inputs, project listing/loading, corrupt manifests, path traversal, UI
  assets and complete create/list/open API flow.
- One pre-existing Starlette/httpx TestClient deprecation warning is non-blocking.
- Desktop Release build and actual native-dialog-to-project-import acceptance:
  **PASS**. See the native design selection checkpoint above.
- Actual authenticated desktop report/shutdown and desktop lifecycle/failure
  smoke tests: **PASS**. See the lifecycle checkpoint above.
- Native Developer-tab smoke including final profile cleanup: **PASS**. Desktop
  and Rhino plug-in Release builds: **PASS, zero warnings/errors**. Browser Edge
  workflow smoke and JavaScript syntax rechecked after the progress display change.
- Actual Dora solve with corrected coordinate units and original numerical/scene
  baseline recheck: **PASS**. Known-size metre/true-mm/corrected-mm geometry with
  nonzero translation and rotation: **PASS** for metrics and metre-space bounds.
- Spark HTTPS transport: **PASS** against the configured server certificate;
  credential-free `/spark/v1/models` returns **401**. Authenticated inference is
  **not yet verified**. Local TLS tests cover pin mismatch, expiry, origin scope
  and redirect rejection without requiring a real provider API key.
- Historical Python-macro launch acceptance: the isolated working `.3dm` opened correctly in
  a new responsive Rhino 8 process on three direct attempts and one `cmd.exe`
  attempt. In all attempts Rhino skipped `/runscript`; no calculation files were
  published. Test-owned Rhino/cmd processes were stopped and no source was saved.
- Current C# acceptance supersedes that startup blocker; see the active
  implementation checkpoints above and `docs/rhino_plugin_verification.json`.

## Known limitations

- File validation currently checks path, extension and content length. Actual
  archive parsing and closed-volume classification now happen during the Rhino
  run; an import-time diagnostic/repair UI is still pending.
- Browser development mode uses typed paths and its own manually launched server;
  native selection and automatic backend launch are available in the desktop.
- Placement supports numeric fields and a constrained XY/Z viewer gizmo. It does
  not yet provide verified plot snapping, north alignment or survey reference points.
- Automatic startup/solve is verified for the baseline and Dora on this machine.
  Dora's mislabelled units are handled through the explicit placement setting;
  genuine millimetre input and nonzero placement have known-size acceptance.
  Users must choose the intended coordinate unit when file metadata is wrong.
  Unsupported geometry and other Rhino versions require further acceptance cases.
  The compatibility Python entry point delegates to C#.
- Recovery/adoption of active Rhino jobs after a hard backend crash is pending.
  Normal desktop shutdown closes owned Rhino processes; cancelled runs and
  completed evidence are persisted. Completed Rhino sessions can be inspected
  while the desktop remains open.
- The desktop still uses the app's `.venv`; bundled Python/installer deployment,
  profile/log retention and clean-machine distribution tests are pending.
- The UI now loads the pre-analysis preview and provides numeric/unit draft
  transforms plus a constrained move/rotate gizmo and local origin/design-center
  controls. Deterministic extents/world-Z/reference-envelope checks are not legal
  plot or ground validation. The attributed PDOK aerial is provisionally aligned
  visual context; the app still lacks approved geographic north, a legal plot,
  ground datum and survey/alignment validation.
- The workflow currently selects only the newest run; there is no historical-run
  chooser yet. If the newest run failed while an older completed run has a scene,
  that older scene is not selectable through the UI. Viewer modules are served
  from the required sibling analyser's locally vendored assets; installer packaging
  must copy/version these assets into the eventual application bundle.
- AI advice now receives the bounded same-run geometry, placement, metrics and four
  controlled images. This transport and response validation are mock-verified, but
  no real provider model has yet demonstrated image understanding in this app.
- Spark TLS verification is complete, but provider authentication, the chosen
  model's vision and `response_format: json_object` support and end-to-end Dutch
  advice have not been verified with real credentials. API keys remain ephemeral; secure saved
  credentials and provider capability checks are pending.

## Not started

- Approved 3D terrain/building context with vertical datum and distribution terms.
- Verified site orientation/reference checks and live multimodal AI acceptance.
- Installer deployment and backend-restart recovery for the Rhino plug-in.
- Calculation migration and scoring.
- Heat-resilience proxy and procedural greenery.
- Secure saved AI credentials.
- Authenticode signing and approved release distribution.

## Exact next tasks

The next release step is installed-machine acceptance of the rebuilt hardened private
tester. Live AI acceptance then requires the user's ephemeral API key and exact
provider model ID. The numbered items below remain the broader product backlog and
historical record.

The Dora scale investigation, known-size unit/placement acceptance, preparation
hang fix and interrupted Developer-tab work are complete. To retest Dora in the
app, restart it, choose **Meters — 1 = 1 m** under Modeleenheid, save the approved
placement and start a new run. Existing historical results are not rewritten.

### 1. Completed: read-only completed-run viewer

- Implemented authenticated `scene.json` rendering with strict metres/Z-up
  validation, four layer controls, orbit/pan/zoom, design/all fit, reset, fixed
  top/front/side views, metre grid/XYZ cues, dimensions and saved transform data.
- Implemented explicit loading/empty/error/WebGL states and project/run-keyed
  cancellation plus GPU disposal. Edge/WebGL and native shell checks pass.
- Remaining orientation gap belongs to task 2: no verified north, plot boundary,
  ground datum or pre-analysis imported geometry is available in this first slice.

### 2. Next build task: pre-analysis placement preview and editing

- **Backend/Rhino foundation completed:** an isolated import-preview export works
  before GH calculation, includes supported visual-only objects, has dedicated
  authenticated API routes and remains separate from analysis runs and metrics.
- **Viewer integration completed:** the latest preview loads in Three.js with
  `PH_VISUAL_ONLY`; numeric/unit changes apply as a design-only delta while context
  stays fixed; preview and immutable last-analysis modes and provenance are explicit.
- **Original gizmo task:** add a constrained move/rotate gizmo plus reset/reference-point
  controls that update the existing numeric fields as an unsaved draft. Saving must
  continue through the current placement endpoint, and a new preview/analysis must
  remain explicit; camera interaction and context geometry must stay unaffected.
- **Gizmo completed:** constrained XY movement and Z rotation, model-origin/design-
  center pivots, restore-saved and world-origin reference controls update the numeric
  fields as an unapproved draft and save only through the existing endpoint. Edge
  pointer/API acceptance and native shell compatibility pass.
- **Original spatial-check task:** add deterministic preview checks for metre-space design
  extents and relationship to viewer world Z=0, with explicit scale/offset warnings.
  First audit available context provenance; keep north, legal plot and ground labels
  unavailable unless versioned source data actually verifies them.
- **Spatial checks completed:** transformed extents, scale thresholds, world-Z and
  available-reference-envelope checks update live and disclose their non-plot/non-
  ground boundary. Context provenance is documented and tested with wrong-scale,
  below/above-Z and far-offset fixtures.
- Add verified plot/height/alignment checks only as validated site data becomes
  available. Expand the versioned context package alongside that work.
- **Acceptance:** verify deliberately offset/rotated/wrong-scale fixtures, approved
  placement persistence and viewer-to-Rhino round trips. Preserve originals and
  never attach old metrics to a newly moved draft.

### 3. Same-run model evidence for AI

- **Original stable-ID task:** extend the Rhino export with stable source-derived design/
  visual object IDs and a bounded geometry summary (classification, metre bounds,
  dimensions and height), preserving layer rendering and historical scene support.
  Define and test ID stability across unchanged previews/runs before adding captures.
- **Stable geometry evidence completed:** preview and analysis jobs contain bounded,
  hashed, run-bound summaries; unchanged repeated Dora previews retain the same 233
  source IDs/object hash, and preview scene layers include optional mesh ranges.
- Extend geometry export with stable object/mass IDs and a structured summary of
  classifications, bounds, dimensions, heights and relevant spatial relationships.
- **Original capture task:** capture actual top, overview perspective, facade-side and
  park-side views from a selected completed run using controlled cameras. Persist
  stable view IDs, camera/visible-layer metadata, image hashes, run/scene/geometry-
  summary hashes and placement in a bounded `view-evidence.json`; reject stale or
  partially captured sets and do not use AI-generated imagery.
- **Controlled captures completed:** fixed real-scene views and a validated,
  atomically published manifest bind images/cameras/layers to run, placement,
  scene, geometry, metrics, source, context and definition hashes. Fixture and live
  baseline Edge acceptance pass.
- Capture actual top, overview, facade-side and park-side views with controlled
  cameras. Store view IDs, camera/up/north metadata, units, placement revision and
  scene/source/run hashes in an evidence manifest.
- Keep images, geometry and metrics tied to one completed run; define bounded
  payload/image sizes and disclose missing/omitted data. These are real scene
  captures, not AI-generated renders.
- **Acceptance:** evidence changes when geometry/placement changes even with the
  same aggregate metrics; missing/stale images cannot be mixed with newer results.

### 4. Model-grounded AI advice and Spark acceptance

- **Implementation completed:** the AI client/request route requires a valid selected-
  run `view-evidence.json` and `geometry-summary.json`, sends a bounded text package
  derived from the controlled views alongside unchanged metrics and geometry data,
  and schema-validates evidence references. Images remain local and are not sent to
  the provider. Mocked tests cover stale/missing evidence, malformed JSON and invented
  object/view/metric references. Do not claim live provider support until tested with
  user credentials.
- Use the deployment endpoint from ignored local configuration with the user's
  credentials and exact model ID. Verify authentication plus real image-input and
  structured-JSON support.
  Capability discovery can proceed earlier, but does not block viewer work.
- Send the model evidence package alongside unmodified Grasshopper metrics and
  the design goal. Validate Dutch observations/recommendations referencing supplied
  object/view IDs and metric fields; distinguish visual inference from measurement.
- Label unsupported vision explicitly. A limited text-only fallback cannot claim
  the model was visually inspected or fulfill the visual-advice acceptance gate.
- **Acceptance:** inspect outgoing requests, test invalid references and stale
  evidence, then verify live advice against the bounded evidence package. A
  credential-free HTTP 401 remains insufficient.
- **Exact next acceptance step:** with the user's API key and exact supported model
  ID, submit verified baseline evidence, inspect the provider response and retain a
  redacted result proving grounded structured JSON support. Until then, live model
  advice remains unverified.

### Later milestones

Procedural greenery, heat-resilience proxy, full reports, installer packaging and
broader Rhino failure/version acceptance remain planned after this visual/model-
evidence foundation. Conceptual AI rendering is excluded for now and is not a
dependency or v1 completion requirement in the revised plan.
