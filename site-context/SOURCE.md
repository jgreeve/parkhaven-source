# ParkHaven aerial context source

- Dataset: Luchtfoto 2025 Ortho 5 en 8cm RGB
- Provider: Landelijke Voorziening Beeldmateriaal, served by PDOK
- WMS: `https://service.pdok.nl/hwh/luchtfotorgb/wms/v1_0`
- Layer: `2025_orthoHR`
- CRS: RD New / EPSG:28992
- Requested extent: E 91340-91940, N 435170-435770
- Requested output: 2500 x 2500 JPEG
- Licence indication in WMS capabilities: open data CC-BY; access constraints none
- Attribution: Bron: Beeldmateriaal Nederland, via PDOK

The RD-to-local transform is the provisional building-aligned fit documented in
`../ParkHaven_Analyzer_App_v0.2/docs/GEOREFERENCE.md`. This package is visual
context, not survey, legal plot, north or ground evidence.
