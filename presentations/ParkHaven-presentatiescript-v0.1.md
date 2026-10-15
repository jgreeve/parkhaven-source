# ParkHaven Studio — 4-minute presentation script

## Slide 1: Opening
ParkHaven Studio turns a Rhino massing model into a traceable design review. The goal is not to replace the designer. It is to connect geometry, repeatable Grasshopper calculations, clear visual evidence, and bounded AI advice in one local workflow. The current prototype already handles a real Parkhaven model, produces controlled views and metrics, and exports an English PDF report. Everything shown today runs around Rhino 8 on the designer's Windows workstation.

## Slide 2: Workflow
The workflow has five controlled steps. First, the designer imports a 3DM file. The app hashes and preserves that source, then works only on a copy. Second, the designer positions the model and approves its units. Third, Rhino and Grasshopper run the analysis. Fourth, the app captures four standardized model views and combines those with calculated metrics for optional AI review. Finally, the app builds a printable report. Each transition has a gate, so incomplete placement, stale evidence, or failed analysis cannot silently flow into the final output.

## Slide 3: Architecture
The architecture is intentionally local-first. The desktop shell starts an authenticated local backend. That backend creates an isolated run folder and launches Rhino visibly, using a packaged Grasshopper definition. Grasshopper writes the scene, geometry summary, and result JSON; the app verifies their hashes before displaying them. Only a bounded text evidence package can go to an OpenAI-compatible endpoint. The model images remain local. This separation makes it clear which values came from deterministic calculation and which statements are AI hypotheses.

## Slide 4: Evidence
This is the evidence layer from the real massa fase 2 model. The exporter gives each analytical mass a stable color: Volume A is blue, B orange, and C purple. The viewer then captures top, overview, facade-side, and park-side cameras at a fixed resolution. Analysis overlays are hidden in those evidence images so the masses remain readable, while the measured results stay available in the dashboard. The report uses the same color legend instead of floating point labels, which makes every referenced volume easy to identify across all views.

## Slide 5: Results
The analysis produces decision-ready screening metrics. In this run the gross floor area is about fifty-one thousand nine hundred square metres, visibility is twenty-four point five percent, and indicative cost is ninety-three point four million euros. The climate screen reports four point three mean sun hours and a maximum UTCI of eighteen point five degrees for one selected weather condition. Foundation screening estimates two hundred forty-nine load-based piles. These are transparent screening values, not final engineering design, and the report labels that limitation explicitly.

## Slide 6: Trust
Trust controls are part of the product, not an afterthought. The original 3DM stays unchanged, and every run carries source, definition, weather, scene, and evidence hashes. A report only accepts advice tied to the current evidence and current policy version. We also found no authoritative plot, access, or tunnel envelope in the available data. Therefore the server rejects advice to shift, widen, set back, or rotate a mass. The AI can propose tests within the current footprint, but it cannot invent site clearance from an aerial photograph.

## Slide 7: Progress
The current build has passed one hundred twenty-seven app tests, twenty-five analyzer tests, real Rhino acceptance, four controlled WebGL captures, installed-bundle smoke testing, and a two-page PDF review. The installer and report workflow are working end to end. The next major step is to add authoritative site constraints, followed by signed distribution and clean-machine acceptance. In short, ParkHaven Studio now provides a usable bridge from Rhino geometry to a review that is visual, measurable, and auditable.
