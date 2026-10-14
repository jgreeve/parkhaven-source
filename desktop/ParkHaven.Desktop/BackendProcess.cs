using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace ParkHaven.Desktop;

internal sealed class BackendProcess
{
    private readonly TaskCompletionSource<Uri> ready = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private readonly object logLock = new();
    private Process? process;
    private bool stopping;
    private readonly Queue<string> recentLog = new();
    private int? launchProcessId;
    private int? backendProcessId;
    private DateTimeOffset? startedAt;
    private DateTimeOffset? exitedAt;
    private int? exitCode;
    public string SessionId { get; } = Guid.NewGuid().ToString("N");
    public string Token { get; } = Convert.ToHexString(RandomNumberGenerator.GetBytes(32)).ToLowerInvariant();
    public string LogPath { get; private set; } = "";
    public bool IsReady { get; private set; }
    public event Action? UnexpectedExit;

    public static string StateDirectory => Environment.GetEnvironmentVariable("PARKHAVEN_STATE_DIR")
        ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ParkHaven");

    private static string FindApplicationRoot()
    {
        var configured = Environment.GetEnvironmentVariable("PARKHAVEN_APP_ROOT");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            var fullPath = Path.GetFullPath(configured);
            if (File.Exists(Path.Combine(fullPath, "app", "desktop_server.py"))) return fullPath;
            throw new InvalidOperationException("PARKHAVEN_APP_ROOT bevat geen ParkHaven-backend.");
        }
        for (var folder = new DirectoryInfo(AppContext.BaseDirectory); folder != null; folder = folder.Parent)
            if (File.Exists(Path.Combine(folder.FullName, "app", "desktop_server.py"))) return folder.FullName;
        throw new InvalidOperationException("De ParkHaven-backend ontbreekt. Herstel de app-map of stel PARKHAVEN_APP_ROOT in.");
    }

    public async Task<Uri> StartAsync(CancellationToken cancellationToken)
    {
        var logs = Path.Combine(StateDirectory, "logs");
        Directory.CreateDirectory(logs);
        LogPath = Path.Combine(logs, $"desktop-{SessionId}.log");
        Log("Desktop-backend starten.");
        var packagedBackend = Path.Combine(AppContext.BaseDirectory, "backend", "ParkHaven.Backend.exe");
        ProcessStartInfo start;
        if (File.Exists(packagedBackend))
        {
            start = new ProcessStartInfo(packagedBackend)
            {
                WorkingDirectory = Path.GetDirectoryName(packagedBackend)!,
            };
            start.Environment["PARKHAVEN_EXPECTED_PLUGIN"] = Path.Combine(
                AppContext.BaseDirectory, "RhinoPlugin", "ParkHaven.Rhino.rhp");
        }
        else
        {
            var root = FindApplicationRoot();
            var python = Environment.GetEnvironmentVariable("PARKHAVEN_PYTHON")
                ?? Path.Combine(root, ".venv", "Scripts", "python.exe");
            if (!File.Exists(python))
                throw new InvalidOperationException("Python ontbreekt. Voer setup_windows.cmd in de app-map uit en probeer opnieuw.");
            start = new ProcessStartInfo(python) { WorkingDirectory = root };
            start.ArgumentList.Add("-u");
            start.ArgumentList.Add("-m");
            start.ArgumentList.Add("app.desktop_server");
            start.Environment["PYTHONIOENCODING"] = "utf-8";
        }
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.RedirectStandardInput = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        process = new Process { StartInfo = start, EnableRaisingEvents = true };
        process.OutputDataReceived += (_, args) => ReceiveReady(args.Data);
        process.ErrorDataReceived += (_, args) => { if (args.Data != null) Log(args.Data); };
        process.Exited += (_, _) =>
        {
            lock (logLock)
            {
                exitedAt = DateTimeOffset.UtcNow;
                try { exitCode = process?.ExitCode; } catch (InvalidOperationException) { }
            }
            Log("Backendproces afgesloten; exitcode " + exitCode + ".");
            ready.TrySetException(new InvalidOperationException("De backend stopte tijdens het starten. Controleer het logbestand en herstel zo nodig de installatie."));
            if (!stopping && IsReady) UnexpectedExit?.Invoke();
        };
        cancellationToken.ThrowIfCancellationRequested();
        if (!process.Start()) throw new InvalidOperationException("De backend kon niet worden gestart.");
        lock (logLock)
        {
            launchProcessId = process.Id;
            startedAt = DateTimeOffset.UtcNow;
        }
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        // The secret travels only through a private pipe, never arguments, URLs or disk.
        await process.StandardInput.WriteLineAsync(JsonSerializer.Serialize(new { token = Token, session_id = SessionId }));
        await process.StandardInput.FlushAsync(cancellationToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(30));
        try
        {
            var uri = await ready.Task.WaitAsync(timeout.Token);
            using var client = new HttpClient(new HttpClientHandler { UseProxy = false });
            using var request = new HttpRequestMessage(HttpMethod.Get, new Uri(uri, "/api/health"));
            request.Headers.Add("X-ParkHaven-Session", Token);
            using var response = await client.SendAsync(request, timeout.Token);
            response.EnsureSuccessStatusCode();
            using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync(timeout.Token));
            if (body.RootElement.GetProperty("status").GetString() != "ok"
                || body.RootElement.GetProperty("version").GetString() != "0.1.0")
                throw new InvalidOperationException("De backend gaf een onverwachte gereedmelding.");
            if (process.HasExited) throw new InvalidOperationException("De backend is onverwacht afgesloten.");
            IsReady = true;
            Log("Backend gereed op " + uri.GetLeftPart(UriPartial.Authority));
            return uri;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw new TimeoutException("De backend was niet binnen 30 seconden gereed. Controleer het logbestand en probeer opnieuw.");
        }
    }

    private void ReceiveReady(string? line)
    {
        if (line == null) return;
        try
        {
            using var json = JsonDocument.Parse(line);
            var root = json.RootElement;
            if (root.GetProperty("event").GetString() != "ready" || root.GetProperty("session_id").GetString() != SessionId)
                throw new InvalidDataException();
            var uri = new Uri(root.GetProperty("url").GetString()!);
            if (uri.Scheme != "http" || uri.Host != "127.0.0.1" || uri.Port <= 0
                || uri.AbsolutePath != "/" || uri.Query != "" || uri.Fragment != "" || uri.UserInfo != "")
                throw new InvalidDataException();
            if (root.TryGetProperty("process_id", out var pid) && pid.TryGetInt32(out var value))
                lock (logLock) backendProcessId = value;
            ready.TrySetResult(uri);
        }
        catch (Exception exception) when (exception is JsonException or InvalidOperationException
            or KeyNotFoundException or UriFormatException or InvalidDataException)
        {
            Log("Onverwacht backendbericht ontvangen.");
        }
    }

    public void Log(string text)
    {
        lock (logLock)
        {
            var line = DateTime.UtcNow.ToString("O") + " " + Redact(text);
            recentLog.Enqueue(line.Length > 8000 ? line[..8000] + "..." : line);
            while (recentLog.Count > 200) recentLog.Dequeue();
            if (LogPath == "") return;
            try { File.AppendAllText(LogPath, line + Environment.NewLine); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    public string Redact(string text)
    {
        text = text.Replace(Token, "[redacted]");
        text = Regex.Replace(text, @"(?i)(bearer\s+)[^\s""',;]+", "$1[redacted]");
        return Regex.Replace(text, @"(?i)((?:api[_-]?key|x-parkhaven-session|token)\s*[""']?\s*[:=]\s*[""']?)[^\s""',;]+", "$1[redacted]");
    }

    public BackendSnapshot Snapshot()
    {
        lock (logLock)
            return new BackendSnapshot(launchProcessId, backendProcessId, startedAt, exitedAt, exitCode,
                IsReady, LogPath, recentLog.ToArray());
    }

    public async Task StopAsync()
    {
        stopping = true;
        if (process == null) return;
        try
        {
            if (!process.HasExited)
            {
                try
                {
                    await process.StandardInput.WriteLineAsync("shutdown");
                    process.StandardInput.Close();
                }
                catch (IOException) { }
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
                try { await process.WaitForExitAsync(timeout.Token); }
                catch (OperationCanceledException)
                {
                    Log("Backend reageert niet op afsluiten; eigen procesboom wordt gestopt.");
                    process.Kill(entireProcessTree: true);
                    await process.WaitForExitAsync();
                }
            }
        }
        catch (InvalidOperationException) { /* Process never started or already exited. */ }
        finally { process.Dispose(); process = null; }
    }
}
