# Contributing

Repository access is limited to approved developers. Changes require focused tests
and review before merging to the protected default branch.

- Never commit imported user `.3dm` files, runtime projects, AI keys or local logs.
- Keep deployment configuration in ignored local files.
- Do not commit `bin`, `obj`, `.venv`, WebView2 profiles or copied Rhino assemblies.
- Preserve source models and keep Grasshopper authoritative for calculated values.
- Record third-party assets, versions, licences and attribution before adding them.
- Run the relevant Python tests and JavaScript syntax checks before review.
- Releases must be built from a reviewed tag and uploaded only to the separate
  private distribution repository.
