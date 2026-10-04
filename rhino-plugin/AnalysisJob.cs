using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization.Metadata;
using Rhino;

namespace ParkHaven.Integration;

internal sealed class AnalysisJob
{
    private readonly string path;
    private readonly Stopwatch stepWatch = new();
    private string? step;
    private long lastProgressMs;
    // JsonArray.Add<T> may create JsonValueCustomized<T> when the net7 plug-in
    // runs inside Rhino's .NET 8 host. Those values require explicit metadata.
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        TypeInfoResolver = new DefaultJsonTypeInfoResolver()
    };
    public JsonObject Data { get; }
    public string Status => Text("status");
    public string JobType => Data["job_type"]?.GetValue<string>() ?? "analysis";
    public bool IsPlacementPreview => JobType == "placement_preview";
    public string Text(string key) => Data[key]?.GetValue<string>()
        ?? throw new InvalidDataException("Ontbrekend jobveld: " + key);

    private AnalysisJob(string path, JsonObject data) { this.path = path; Data = data; }

    public static AnalysisJob Read(string path)
    {
        var data = JsonNode.Parse(File.ReadAllText(path)) as JsonObject
            ?? throw new InvalidDataException("Ongeldig jobbestand.");
        var jobType = data["job_type"]?.GetValue<string>() ?? "analysis";
        if (data["schema_version"]?.GetValue<int>() != 1 || jobType is not ("analysis" or "placement_preview"))
            throw new InvalidDataException("Onbekende jobversie of jobsoort.");
        if (jobType == "analysis" && data["placement"]?["approved"]?.GetValue<bool>() != true)
            throw new InvalidDataException("Plaatsing is niet goedgekeurd voor analyse.");
        var job = new AnalysisJob(Path.GetFullPath(path), data);
        var directory = Path.GetDirectoryName(Path.GetFullPath(path))!;
        var localPaths = jobType == "analysis"
            ? new[] { "working_model", "definition", "definition_runtime_path", "data_dir" }
            : new[] { "working_model", "data_dir" };
        foreach (var key in localPaths)
            if (!Path.GetFullPath(job.Text(key)).StartsWith(directory + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Runbestand valt buiten de runmap: " + key);
        return job;
    }

    public bool MatchesDocument(RhinoDoc doc) => !string.IsNullOrEmpty(doc.Path) &&
        string.Equals(Path.GetFullPath(doc.Path), Path.GetFullPath(Text("working_model")), StringComparison.OrdinalIgnoreCase);

    public void RecordRuntime()
    {
        Data["runtime"] = new JsonObject
        {
            ["rhino"] = RhinoApp.Version.ToString(),
            ["plugin"] = typeof(AnalysisJob).Assembly.GetName().Version!.ToString(),
            ["dotnet"] = Environment.Version.ToString(),
            ["process_id"] = Process.GetCurrentProcess().Id
        };
        Save();
    }

    public void SetStatus(string status)
    {
        if (Status != status) Data["phase_started_at"] = DateTime.UtcNow.ToString("O");
        Data["status"] = status;
        Save();
    }

    public void BeginStep(string name, string detail)
    {
        if (step != null)
        {
            var timings = Data["step_seconds"] as JsonObject ?? new JsonObject();
            Data["step_seconds"] = timings;
            timings[step] = Math.Round(stepWatch.Elapsed.TotalSeconds, 3);
        }
        step = name;
        stepWatch.Restart();
        lastProgressMs = 0;
        Data["progress_step"] = name;
        Data["progress_detail"] = detail;
        Data["progress_at"] = DateTime.UtcNow.ToString("O");
        Save();
    }

    public void ReportProgress(string detail, bool force = false)
    {
        if (!force && stepWatch.ElapsedMilliseconds - lastProgressMs < 500) return;
        lastProgressMs = stepWatch.ElapsedMilliseconds;
        Data["progress_detail"] = detail;
        Data["progress_at"] = DateTime.UtcNow.ToString("O");
        Save();
    }

    public void Fail(Exception ex)
    {
        Data["error"] = ex.Message;
        Data["traceback"] = ex.ToString();
        SetStatus("failed");
    }

    public void Save()
    {
        Data["updated_at"] = DateTime.UtcNow.ToString("O");
        var temporary = path + ".plugin.tmp";
        File.WriteAllText(temporary, Data.ToJsonString(JsonOptions));
        // Windows readers may briefly hold job.json without FILE_SHARE_DELETE.
        // Keep publication atomic, but allow an in-flight backend poll to close it.
        for (int attempt = 0; ; attempt++)
        {
            try { File.Move(temporary, path, true); break; }
            catch (Exception ex) when (attempt < 10 && ex is IOException or UnauthorizedAccessException)
            {
                Thread.Sleep(25 * (attempt + 1));
            }
        }
    }
}
