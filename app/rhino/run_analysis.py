"""Legacy RunPythonScript entry point; all analysis belongs to the C# plug-in."""

import Rhino

if not Rhino.RhinoApp.RunScript("_ParkHavenAnalyze", False):
    raise RuntimeError("ParkHavenAnalyze kon niet worden gestart. Installeer de Rhino-plug-in.")
