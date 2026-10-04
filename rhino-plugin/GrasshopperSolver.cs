using System.Runtime.CompilerServices;
using System.Text.Json.Nodes;
using GH_IO.Serialization;
using Grasshopper;
using Grasshopper.Kernel;

namespace ParkHaven.Integration;

internal static class GrasshopperSolver
{
    // Defer loading GH assemblies until Rhino has loaded the Grasshopper plug-in.
    [MethodImpl(MethodImplOptions.NoInlining)]
    public static void Solve(AnalysisJob job)
    {
        job.SetStatus("solving");
        job.BeginStep("solve", "Grasshopper-definitie laden en berekenen");
        job.Data["runtime"]!["grasshopper"] = typeof(GH_Document).Assembly.GetName().Version!.ToString();
        bool previous = GH_Document.EnableSolutions;
        using var document = new GH_Document();
        try
        {
            GH_Document.EnableSolutions = false;
            var archive = new GH_Archive();
            if (!archive.ReadFromFile(job.Text("definition")) || !archive.ExtractObject(document, "Definition"))
                throw new InvalidDataException("Grasshopper-definitie kon niet worden geladen.");
            document.FilePath = job.Text("definition_runtime_path");
            Instances.DocumentServer.AddDocument(document);
            if (Instances.ActiveCanvas != null) Instances.ActiveCanvas.Document = document;
            document.Enabled = true;
            GH_Document.EnableSolutions = true;
            document.NewSolution(true);
            var errors = new List<string>();
            foreach (var component in document.Objects.OfType<IGH_ActiveObject>())
            {
                errors.AddRange(component.RuntimeMessages(GH_RuntimeMessageLevel.Error));
                foreach (var warning in component.RuntimeMessages(GH_RuntimeMessageLevel.Warning))
                    ((JsonArray)job.Data["warnings"]!).Add(JsonValue.Create(warning));
            }
            if (errors.Count > 0) throw new InvalidOperationException(string.Join("; ", errors));
            var metrics = JsonNode.Parse(File.ReadAllText(Path.Combine(job.Text("data_dir"), "latest.json")))!;
            foreach (var key in new[] { "bvo_m2", "sight_pct", "indicative_cost_eur" })
                if (metrics[key] is not JsonValue value || !value.TryGetValue<double>(out var number) || !double.IsFinite(number))
                    throw new InvalidDataException("Grasshopper leverde geen geldige waarde voor " + key);
            var scene = JsonNode.Parse(File.ReadAllText(Path.Combine(job.Text("data_dir"), "scene.json")))!;
            if (scene["layers"] is not JsonArray layers || layers.Count == 0)
                throw new InvalidDataException("Grasshopper leverde geen geldige 3D-scene.");
            job.Save();
        }
        finally
        {
            // Freeze the completed evidence: later manual model edits cannot rewrite it.
            document.Enabled = false;
            Instances.DocumentServer.RemoveDocument(document);
            GH_Document.EnableSolutions = previous;
        }
    }
}
