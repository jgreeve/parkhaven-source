using System.Text.Json.Serialization;

namespace ParkHaven.Desktop;

internal sealed record BackendSnapshot(int? LaunchProcessId, int? ProcessId, DateTimeOffset? StartedAt,
    DateTimeOffset? ExitedAt, int? ExitCode, bool WasReady, string LogPath, string[] Log)
{
    public bool Running => StartedAt.HasValue && !ExitedAt.HasValue;
}

internal sealed class DeveloperStatus
{
    [JsonPropertyName("server_time")] public string ServerTime { get; set; } = "";
    [JsonPropertyName("process_id")] public int ProcessId { get; set; }
    [JsonPropertyName("uptime_seconds")] public double UptimeSeconds { get; set; }
    [JsonPropertyName("runs")] public List<RunDiagnostic> Runs { get; set; } = new();
    [JsonPropertyName("warnings")] public List<string> Warnings { get; set; } = new();
}

internal sealed class RunDiagnostic
{
    [JsonPropertyName("project_id")] public string ProjectId { get; set; } = "";
    [JsonPropertyName("project_name")] public string ProjectName { get; set; } = "";
    [JsonPropertyName("run_id")] public string RunId { get; set; } = "";
    [JsonPropertyName("status")] public string Status { get; set; } = "";
    [JsonPropertyName("created_at")] public string CreatedAt { get; set; } = "";
    [JsonPropertyName("updated_at")] public string UpdatedAt { get; set; } = "";
    [JsonPropertyName("phase_started_at")] public string PhaseStartedAt { get; set; } = "";
    [JsonPropertyName("progress_step")] public string ProgressStep { get; set; } = "";
    [JsonPropertyName("progress_detail")] public string ProgressDetail { get; set; } = "";
    [JsonPropertyName("progress_at")] public string ProgressAt { get; set; } = "";
    [JsonPropertyName("step_seconds")] public Dictionary<string, double> StepSeconds { get; set; } = new();
    [JsonPropertyName("rhino_process_id")] public int? RhinoProcessId { get; set; }
    [JsonPropertyName("error")] public string Error { get; set; } = "";
    [JsonPropertyName("warnings")] public List<string> Warnings { get; set; } = new();
    public bool Active => Status is "launch_requested" or "runner_started" or "preparing_model" or "solving";
    public string Stage => Status switch
    {
        "prepared" => "Voorbereid (niet gestart)", "launch_requested" => "Rhino starten",
        "runner_started" => "Plug-in gestart", "preparing_model" => "Model voorbereiden",
        "solving" => "Grasshopper rekent", "completed" => "Voltooid", "failed" => "Mislukt",
        "cancelled" => "Geannuleerd", _ => "Onbekend: " + Status
    };
    public string UpdatedLabel => DateTimeOffset.TryParse(UpdatedAt, out var date) ? date.ToLocalTime().ToString("dd-MM HH:mm:ss") : "Onbekend";
    public string PhaseAge => Active && DateTimeOffset.TryParse(string.IsNullOrEmpty(PhaseStartedAt) ? UpdatedAt : PhaseStartedAt, out var date)
        ? $"{Math.Max(0, (DateTimeOffset.UtcNow - date).TotalSeconds):0} s" : "—";
    public string Details => $"Project: {ProjectName}\nProject-ID: {ProjectId}\nRun-ID: {RunId}\n"
        + $"Fase: {Stage} ({Status})\nGestart/aangemaakt: {CreatedAt}\nLaatste wijziging: {UpdatedAt}\n"
        + $"Stap: {ProgressStep}\nVoortgang: {ProgressDetail}\nLaatste voortgang: {ProgressAt}\n"
        + "Gemeten stappen: " + string.Join(" · ", StepSeconds.Select(step => $"{step.Key}: {step.Value:0.###} s")) + "\n"
        + $"Rhino PID (geregistreerd): {RhinoProcessId?.ToString() ?? "onbekend"}\n"
        + "Fout: " + (string.IsNullOrEmpty(Error) ? "geen" : Error) + "\nWaarschuwingen: "
        + (Warnings.Count == 0 ? "geen" : string.Join("\n", Warnings));
}
