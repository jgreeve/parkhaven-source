using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;

namespace ParkHaven.Desktop;

public partial class MainWindow
{
    private readonly DispatcherTimer diagnosticsTimer = new() { Interval = TimeSpan.FromSeconds(2) };
    private readonly HttpClient diagnosticsClient = new(new HttpClientHandler { UseProxy = false })
        { Timeout = Timeout.InfiniteTimeSpan };
    private bool diagnosticsBusy;
    private string? diagnosticsSession;
    private DateTimeOffset? lastBackendResponse;
    private List<RunDiagnostic> lastRuns = new();

    private void StartDiagnostics()
    {
        diagnosticsTimer.Tick += async (_, _) => await RefreshDiagnosticsAsync();
        diagnosticsTimer.Start();
        _ = RefreshDiagnosticsAsync();
    }

    private void RenderBackendSnapshot(BackendSnapshot? snapshot)
    {
        var process = snapshot == null ? "Backendproces nog niet aangemaakt."
            : $"Desktop PID: {Environment.ProcessId} · Python launcher PID: {snapshot.LaunchProcessId?.ToString() ?? "—"}"
                + $" · Backend PID: {snapshot.ProcessId?.ToString() ?? "—"}\n"
                + $"Gestart: {snapshot.StartedAt?.ToLocalTime().ToString("dd-MM HH:mm:ss") ?? "—"}"
                + $" · Gestopt: {snapshot.ExitedAt?.ToLocalTime().ToString("dd-MM HH:mm:ss") ?? "—"}";
        DeveloperProcess.Text = process;
        DeveloperLogPath.Text = "Logbestand: " + (string.IsNullOrEmpty(snapshot?.LogPath) ? "nog niet beschikbaar" : snapshot.LogPath);
        var log = snapshot == null ? "Nog geen backendlog." : string.Join(Environment.NewLine, snapshot.Log);
        if (DeveloperLog.Text != log)
        {
            DeveloperLog.Text = log;
            DeveloperLog.ScrollToEnd();
        }
    }

    private void SetBackendState(string message, bool healthy)
    {
        DeveloperBackendStatus.Text = message;
        DeveloperBackendStatus.Foreground = healthy ? Brushes.DarkGreen : Brushes.DarkRed;
        BackendBadge.Text = "Backend: " + message;
    }

    private void RenderHeartbeat(string check)
    {
        DeveloperHeartbeat.Text = $"Laatste controle: {DateTimeOffset.Now:HH:mm:ss} · {check}\nLaatste succesvol antwoord: "
            + (lastBackendResponse.HasValue
                ? $"{lastBackendResponse.Value.ToLocalTime():HH:mm:ss} ({Math.Max(0, (DateTimeOffset.UtcNow - lastBackendResponse.Value).TotalSeconds):0} s geleden)"
                : "nog geen");
    }

    private void RenderRuns(bool fresh)
    {
        var selected = (DeveloperRuns.SelectedItem as RunDiagnostic)?.RunId;
        DeveloperRuns.ItemsSource = lastRuns;
        DeveloperRuns.Items.Refresh(); // Refresh time-in-phase without inventing progress events.
        DeveloperRuns.SelectedItem = lastRuns.FirstOrDefault(run => run.RunId == selected) ?? lastRuns.FirstOrDefault();
        if (lastRuns.Count == 0) DeveloperRunDetails.Text = "Nog geen analyse geregistreerd.";
        int active = lastRuns.Count(run => run.Active);
        DeveloperRunSummary.Text = $"{lastRuns.Count} recente runs · {active} actief"
            + (fresh ? " · actuele backendrespons" : " · laatst bekende gegevens; niet live bevestigd");
        AnalysisActivity.IsIndeterminate = fresh && active > 0;
    }

    private async Task RefreshDiagnosticsAsync()
    {
        if (diagnosticsBusy || closing) return;
        diagnosticsBusy = true;
        var owned = backend;
        try
        {
            if (diagnosticsSession != owned?.SessionId)
            {
                diagnosticsSession = owned?.SessionId;
                lastBackendResponse = null;
                lastRuns = new();
                DeveloperNotice.Text = "";
            }
            var snapshot = owned?.Snapshot();
            RenderBackendSnapshot(snapshot);
            if (owned == null || snapshot == null || !snapshot.Running || !snapshot.WasReady || appUri == null)
            {
                SetBackendState(snapshot?.ExitedAt != null
                    ? $"Gestopt · exitcode {snapshot.ExitCode?.ToString() ?? "onbekend"}"
                    : starting ? "Bezig met starten..." : "Niet gestart", false);
                RenderHeartbeat("Geen actieve HTTP-verbinding");
                RenderRuns(false);
                return;
            }

            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token);
            timeout.CancelAfter(TimeSpan.FromSeconds(2));
            using var request = new HttpRequestMessage(HttpMethod.Get, new Uri(appUri, "/api/developer/status"));
            request.Headers.Add("X-ParkHaven-Session", owned.Token);
            var watch = Stopwatch.StartNew();
            using var response = await diagnosticsClient.SendAsync(request, timeout.Token);
            response.EnsureSuccessStatusCode();
            var status = JsonSerializer.Deserialize<DeveloperStatus>(await response.Content.ReadAsStringAsync(timeout.Token))
                ?? throw new JsonException("Geen diagnostische gegevens ontvangen.");
            if (closing || !ReferenceEquals(backend, owned)) return;
            lastBackendResponse = DateTimeOffset.UtcNow;
            lastRuns = status.Runs;
            SetBackendState("Actief · HTTP reageert", true);
            RenderHeartbeat($"Antwoord in {watch.ElapsedMilliseconds} ms · uptime {status.UptimeSeconds:0} s");
            DeveloperNotice.Text = owned.Redact(string.Join("\n", status.Warnings));
            RenderRuns(true);
        }
        catch (Exception exception) when (exception is HttpRequestException or OperationCanceledException or JsonException)
        {
            if (closing || !ReferenceEquals(backend, owned)) return;
            var snapshot = owned?.Snapshot();
            RenderBackendSnapshot(snapshot);
            SetBackendState(snapshot?.ExitedAt != null
                ? $"Gestopt · exitcode {snapshot.ExitCode?.ToString() ?? "onbekend"}"
                : "Geen HTTP-antwoord · proces niet als gestopt gemeld", false);
            RenderHeartbeat("Controle mislukt");
            DeveloperNotice.Text = exception is OperationCanceledException
                ? "Geen antwoord binnen 2 seconden. De backend kan bezet of vastgelopen zijn; dit bewijst geen crash."
                : owned?.Redact(exception.Message) ?? "Backend niet bereikbaar.";
            RenderRuns(false);
        }
        finally { diagnosticsBusy = false; }
    }

    private async void OnRefreshDiagnostics(object sender, RoutedEventArgs args) => await RefreshDiagnosticsAsync();

    private void OnRunDiagnosticSelected(object sender, SelectionChangedEventArgs args)
    {
        if (DeveloperRunDetails != null && DeveloperRuns.SelectedItem is RunDiagnostic run)
            DeveloperRunDetails.Text = backend?.Redact(run.Details) ?? run.Details;
    }

    private void OnCopyDiagnostics(object sender, RoutedEventArgs args)
    {
        var text = string.Join("\n\n", DeveloperBackendStatus.Text, DeveloperProcess.Text, DeveloperHeartbeat.Text,
            DeveloperLogPath.Text, DeveloperNotice.Text, DeveloperRunSummary.Text,
            string.Join("\n\n", lastRuns.Select(run => run.Details)), DeveloperLog.Text);
        try
        {
            Clipboard.SetText(backend?.Redact(text) ?? text);
            DeveloperNotice.Text = "Diagnostiek gekopieerd.";
        }
        catch (System.Runtime.InteropServices.ExternalException)
        {
            DeveloperNotice.Text = "Klembord is in gebruik. Probeer opnieuw.";
        }
    }

    private void OnOpenLogDirectory(object sender, RoutedEventArgs args)
    {
        var path = backend?.LogPath;
        if (string.IsNullOrEmpty(path)) { DeveloperNotice.Text = "Nog geen logmap beschikbaar."; return; }
        try
        {
            var start = new ProcessStartInfo("explorer.exe") { UseShellExecute = false };
            start.ArgumentList.Add(Path.GetDirectoryName(path)!);
            Process.Start(start);
        }
        catch (System.ComponentModel.Win32Exception)
        {
            DeveloperNotice.Text = "De logmap kon niet worden geopend.";
        }
    }
}
