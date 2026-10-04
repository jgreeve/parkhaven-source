using System.Text.Json.Nodes;
using ParkHaven.Integration;

// Exercise the actual net7-compiled serializer in the .NET 8 host, without
// starting Rhino or calling any native RhinoCommon geometry entry points.
var directory = Path.Combine(Path.GetTempPath(), "opencode", "parkhaven-serialization-" + Guid.NewGuid());
Directory.CreateDirectory(directory);
try
{
    var path = Path.Combine(directory, "job.json");
    File.WriteAllText(path, new JsonObject
    {
        ["schema_version"] = 1, ["status"] = "prepared",
        ["placement"] = new JsonObject { ["approved"] = true },
        ["working_model"] = Path.Combine(directory, "design.3dm"),
        ["definition"] = Path.Combine(directory, "analysis.ghx"),
        ["definition_runtime_path"] = Path.Combine(directory, "analysis.gh"),
        ["data_dir"] = Path.Combine(directory, "data"), ["warnings"] = new JsonArray()
    }.ToJsonString());
    var job = AnalysisJob.Read(path);
    job.SetStatus("preparing_model");
    var phaseStart = job.Text("phase_started_at");
    job.BeginStep("classify_design", "Ontwerp controleren");
    // This generic overload is the original Dora-triggered failure path.
    ((JsonArray)job.Data["warnings"]!).Add<string>("2 objecten zijn alleen visueel; één open oppervlak.");
    job.Save();
    var saved = JsonNode.Parse(File.ReadAllText(path))!;
    if (saved["warnings"]![0]!.GetValue<string>() != "2 objecten zijn alleen visueel; één open oppervlak.")
        throw new Exception("Warning did not round-trip");
    job.ReportProgress("Object 233/233", true);
    if (job.Text("phase_started_at") != phaseStart) throw new Exception("Progress reset phase age");
    job.BeginStep("read_context", "Context lezen");
    if (job.Data["step_seconds"]?["classify_design"] == null) throw new Exception("Missing step timing");
    job.Fail(new InvalidOperationException("Deliberate failure after a classification warning"));
    saved = JsonNode.Parse(File.ReadAllText(path))!;
    if (saved["status"]!.GetValue<string>() != "failed" || saved["error"]!.GetValue<string>() !=
        "Deliberate failure after a classification warning" || saved["warnings"]!.AsArray().Count != 1)
        throw new Exception("Failure after warning did not persist");

    var previewPath = Path.Combine(directory, "preview.json");
    File.WriteAllText(previewPath, new JsonObject
    {
        ["schema_version"] = 1, ["job_type"] = "placement_preview", ["status"] = "prepared",
        ["placement"] = new JsonObject { ["approved"] = false },
        ["working_model"] = Path.Combine(directory, "preview.3dm"),
        ["data_dir"] = Path.Combine(directory, "preview-data"), ["warnings"] = new JsonArray()
    }.ToJsonString());
    var preview = AnalysisJob.Read(previewPath);
    if (!preview.IsPlacementPreview) throw new Exception("Preview job type was not recognized");
    Console.WriteLine("PASS: warning serialization, preview validation, failure publication, step timing and stable phase age.");
}
finally { Directory.Delete(directory, true); }
