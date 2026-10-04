# ParkHaven context provenance boundary

Audit date: 2026-10-02.

## Runtime evidence

Desktop preview and completed-run scenes use only these analysis-reference layers
from the hashed `ParkHaven_MVP.3dm` snapshot:

- `PH_FACADES`
- `PH_TARGET`
- `REFERENCE_CONTEXT`

They are exported in local metres with Rhino Z-up. Every job records the reference
model SHA-256. These layers support visual orientation and deterministic envelope
comparisons; they are not a legal site package.

The viewer additionally loads a separate visual-only aerial package:

- PDOK layer `2025_orthoHR`, clipped to RD New extent E 91340-91940 and
  N 435170-435770;
- 2500 x 2500 JPEG, pinned by SHA-256 in `site-context/manifest.json`;
- transformed offline into local metre coordinates using the provisional
  building-aligned fit documented in `GEOREFERENCE.md`;
- displayed at visual Z=-0.15 m and never imported into Rhino, Grasshopper or
  deterministic checks;
- attributed in the UI as `Bron: Beeldmateriaal Nederland, via PDOK`.

The package manifest, image and alignment metadata are validated by the backend.
Controlled model captures include `PDOK_AERIAL` and bind both context manifest and
image hashes. Changing the package invalidates older captures until they are remade.

## Explicitly unavailable

- No legal plot boundary is exported or versioned for desktop use.
- No approved ground/maaiveld datum is exported.
- No approved geographic-north transform is included in the scene contract. The
  aerial's 1.735-degree provisional grid-north relation is display metadata only.
- Hidden Forma site limits, property boundaries and terrain identified in the source
  audit are not analysis-reference layers and are not runtime validation evidence.

The analyser's `docs/GEOREFERENCE.md` contains a strong map-derived provisional RD
New alignment, but it explicitly is not a survey control and is not yet an approved,
versioned desktop context transform. The desktop must not turn that document into a
confirmed north, plot or ground claim.

## Allowed checks

With the attributed but provisionally aligned aerial package, the desktop may report:

- exact metre-space design bounds and dimensions from the loaded scene;
- whether design geometry is below, across or above viewer world Z=0;
- scale warnings using documented thresholds;
- XY overlap or distance relative to the combined available reference-layer
  envelope.

All such results must be labelled as coordinate/reference-envelope checks, not plot,
ground, survey or legal validation.
