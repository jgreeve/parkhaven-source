# Third-party and data notices

This file is a distribution checklist, not a complete public release notice yet.

## PDOK aerial imagery

The visual site context is sourced from `Luchtfoto 2025 Ortho 5 en 8cm RGB`,
Landelijke Voorziening Beeldmateriaal via PDOK. Source and retrieval parameters are
recorded in `site-context/SOURCE.md`. Service metadata identifies the data as
CC-BY, but the exact licence version and cached-redistribution terms must be
confirmed before an end-user release. Required attribution:

`Bron: Beeldmateriaal Nederland, via PDOK`

## Three.js

The standalone tester package bundles the pinned Three.js 0.180.0 viewer files and
OrbitControls from the analyser workspace. Three.js is MIT-licensed and its upstream
licence is included beside those files.

## pythermalcomfort UTCI implementation

The native Grasshopper UTCI screening ports the standard UTCI approximation
from the MIT-licensed `pythermalcomfort` implementation. Copyright (c) 2019
Federico Tartarini. The upstream source and licence are available at
<https://github.com/CenterForTheBuiltEnvironment/pythermalcomfort>.

## Rotterdam-Geulhaven TMYx weather data

The tester bundles the Rotterdam-Geulhaven EPW typical meteorological year from
Climate.OneBuilding.Org. The exact source URL, retrieval date and SHA-256 are
recorded in the bundled `weather/README.md`. Confirm the upstream data licence
and cached-redistribution terms before an external release.

## Microsoft WebView2

The desktop uses the Microsoft.Web.WebView2 NuGet package. The tester installer
includes Microsoft's Evergreen bootstrapper and invokes it during installation.
Preserve the applicable Microsoft notices and verify the supported Evergreen
Runtime distribution model before an external release.

## Inno Setup

The Windows installer is built with Inno Setup 6.7.3. The compiler reports itself
as non-commercial-use-only unless an applicable commercial licence has been
purchased. Confirm that licence before any commercial distribution.

## Rhino and Grasshopper

RhinoCommon, Grasshopper and GH_IO are referenced from an installed, licensed
Rhino 8 environment. Rhino, Grasshopper and copied Rhino assemblies are not granted
for redistribution by this repository. Confirm McNeel terms before packaging and
require users to install and license Rhino independently unless separately approved.
