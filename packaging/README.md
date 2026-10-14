# Tester installer

Build the private Windows x64 tester installer from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\build_tester.ps1
```

The build downloads a hash-pinned app-local .NET 8 SDK, Inno Setup 6, Python 3.13 build
environment and the Microsoft WebView2 Evergreen bootstrapper when they
are not already available. Python build dependencies are version- and hash-locked;
downloaded executable tools are hash- or publisher-verified. Tools and generated
payloads are ignored by Git. Rhino 8 must be installed at its standard 64-bit path
both when building the plug-in and when installing ParkHaven.

Outputs are written to `artifacts/`. The installer is per-user, registers the
ParkHaven Rhino plug-in under HKCU, installs or updates WebView2 silently, and does
not bundle Rhino or McNeel assemblies. The installer is unsigned unless a separate
approved signing step is applied before distribution. Confirm that the applicable
Inno Setup licence is in place before using this pipeline for commercial releases.

When `config/ai-trust.local.json` exists, the private tester includes that deployment
profile and its referenced public certificates. The files remain ignored source-tree
inputs and the build rejects private keys, missing files and paths outside `config/`.
