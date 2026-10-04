# Third-party and data notices

This file is a distribution checklist, not a complete release notice yet.

## PDOK aerial imagery

The visual site context is sourced from `Luchtfoto 2025 Ortho 5 en 8cm RGB`,
Landelijke Voorziening Beeldmateriaal via PDOK. Source and retrieval parameters are
recorded in `site-context/SOURCE.md`. Service metadata identifies the data as
CC-BY, but the exact licence version and cached-redistribution terms must be
confirmed before an end-user release. Required attribution:

`Bron: Beeldmateriaal Nederland, via PDOK`

## Three.js

The viewer currently loads Three.js 0.180.0 and OrbitControls from the sibling
analyser workspace. Three.js is MIT-licensed. A standalone release must bundle the
pinned files and their upstream MIT licence; they are not yet contained here.

## Microsoft WebView2

The desktop uses the Microsoft.Web.WebView2 NuGet package. Preserve the applicable
Microsoft notices and verify the supported Evergreen Runtime distribution model.

## Rhino and Grasshopper

RhinoCommon, Grasshopper and GH_IO are referenced from an installed, licensed
Rhino 8 environment. Rhino, Grasshopper and copied Rhino assemblies are not granted
for redistribution by this repository. Confirm McNeel terms before packaging and
require users to install and license Rhino independently unless separately approved.
