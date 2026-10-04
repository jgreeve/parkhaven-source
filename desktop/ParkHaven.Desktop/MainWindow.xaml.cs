using System;
using System.ComponentModel;
using System.IO;
using System.Text.Json;
using System.Windows;
using Microsoft.Web.WebView2.Core;
using Microsoft.Win32;

namespace ParkHaven.Desktop;

public partial class MainWindow : Window
{
    private Uri? appUri;
    private bool pickerOpen;
    private BackendProcess? backend;
    private CoreWebView2Environment? environment;
    private readonly CancellationTokenSource lifetime = new();
    private readonly List<Window> reportWindows = new();
    private Task startup = Task.CompletedTask;
    private bool starting;
    private bool closing;
    private bool shutdownComplete;

    public MainWindow()
    {
        InitializeComponent();
        Loaded += (_, _) =>
        {
            startup = StartApplicationAsync();
            StartDiagnostics();
        };
    }

    private async Task StartApplicationAsync()
    {
        if (starting || closing) return;
        starting = true;
        RetryStartup.Visibility = Visibility.Collapsed;
        ShowStatus("ParkHaven wordt gestart", "Lokale backend starten...");
        try
        {
            foreach (var window in reportWindows.ToArray()) window.Close();
            appUri = null;
            if (backend != null) await backend.StopAsync();
            backend = new BackendProcess();
            var owned = backend;
            owned.UnexpectedExit += () => Dispatcher.BeginInvoke(new Action(() =>
            {
                if (!closing && !starting && ReferenceEquals(backend, owned))
                {
                    ShowStatus("Verbinding met de backend verloren", "De backend is onverwacht gestopt.\nLogbestand: " + owned.LogPath);
                    RetryStartup.Visibility = Visibility.Visible;
                }
            }));
            appUri = await owned.StartAsync(lifetime.Token);
            lifetime.Token.ThrowIfCancellationRequested();
            FailureMessage.Text = "Lokale interface laden...";
            if (environment == null)
            {
                // Separate runtime profile prevents two app windows sharing WebView processes/state.
                var profile = Path.Combine(BackendProcess.StateDirectory, "WebView2", Guid.NewGuid().ToString("N"));
                environment = await CoreWebView2Environment.CreateAsync(userDataFolder: profile);
            }
            if (AppView.CoreWebView2 == null)
            {
                await AppView.EnsureCoreWebView2Async(environment);
                ConfigureWebView(AppView.CoreWebView2 ?? throw new InvalidOperationException("WebView2 is niet beschikbaar."));
                AppView.CoreWebView2.WebMessageReceived += OnWebMessage;
                AppView.CoreWebView2.NavigationCompleted += (_, navigation) =>
                {
                    if (closing) return;
                    if (navigation.IsSuccess)
                    {
                        FailurePanel.Visibility = Visibility.Collapsed;
                        AppView.Visibility = Visibility.Visible;
                    }
                    else
                    {
                        ShowStatus("De interface kon niet laden", "Controleer het backendlog en probeer opnieuw.");
                        RetryStartup.Visibility = Visibility.Visible;
                    }
                };
            }
            lifetime.Token.ThrowIfCancellationRequested();
            AppView.CoreWebView2.Navigate(appUri.AbsoluteUri);
        }
        catch (OperationCanceledException) when (closing) { }
        catch (Exception exception)
        {
            backend?.Log(exception.Message);
            if (backend != null) await backend.StopAsync();
            if (!closing)
            {
                ShowStatus("ParkHaven kon niet starten", exception.Message + "\nLogbestand: " + backend?.LogPath);
                RetryStartup.Visibility = Visibility.Visible;
            }
        }
        finally { starting = false; }
    }

    private void ShowStatus(string title, string message)
    {
        FailureTitle.Text = title;
        FailureMessage.Text = message;
        FailurePanel.Visibility = Visibility.Visible;
        AppView.Visibility = Visibility.Hidden;
    }

    private void OnRetryStartup(object sender, RoutedEventArgs args) => startup = StartApplicationAsync();

    private void ConfigureWebView(CoreWebView2 core)
    {
        core.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
        core.WebResourceRequested += (_, args) =>
        {
            if (backend != null && IsAppOrigin(args.Request.Uri))
                args.Request.Headers.SetHeader("X-ParkHaven-Session", backend.Token);
            else
                args.Response = core.Environment.CreateWebResourceResponse(Stream.Null, 403, "Forbidden", "");
        };
        core.NavigationStarting += (_, args) => { if (!IsAppOrigin(args.Uri)) args.Cancel = true; };
        core.NewWindowRequested += OnNewWindow;
    }

    private void OnNewWindow(object? sender, CoreWebView2NewWindowRequestedEventArgs args)
    {
        args.Handled = true;
        if (!IsAppOrigin(args.Uri) || closing) return;
        var uri = args.Uri;
        // Create the WPF window outside WebView2's callback/message loop.
        Dispatcher.BeginInvoke(new Action(async () => await OpenReportAsync(uri)));
    }

    private async Task OpenReportAsync(string uri)
    {
        if (closing || !IsAppOrigin(uri)) return;
        var view = new Microsoft.Web.WebView2.Wpf.WebView2();
        var window = new Window { Title = "ParkHaven rapport", Width = 1000, Height = 800, Owner = this, Content = view };
        reportWindows.Add(window);
        window.Closed += (_, _) => { view.Dispose(); reportWindows.Remove(window); };
        try
        {
            window.Show();
            await view.EnsureCoreWebView2Async(environment);
            ConfigureWebView(view.CoreWebView2);
            view.CoreWebView2.Navigate(uri);
        }
        catch (Exception exception)
        {
            backend?.Log("Rapportvenster: " + exception.Message);
            window.Close();
        }
    }

    private bool IsAppOrigin(string source) => appUri != null
        && Uri.TryCreate(source, UriKind.Absolute, out var uri)
        && uri.Scheme == appUri.Scheme && uri.IdnHost == appUri.IdnHost && uri.Port == appUri.Port;

    private void OnWebMessage(object? sender, CoreWebView2WebMessageReceivedEventArgs args)
    {
        var source = args.Source;
        if (pickerOpen || !IsAppOrigin(source)) return;
        string requestId;
        try
        {
            using var message = JsonDocument.Parse(args.WebMessageAsJson);
            var root = message.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || !root.TryGetProperty("type", out var type) || type.GetString() != "parkhaven.pickDesign"
                || !root.TryGetProperty("requestId", out var id) || !Guid.TryParse(id.GetString(), out _)) return;
            requestId = id.GetString()!;
        }
        catch (Exception exception) when (exception is JsonException or InvalidOperationException)
        {
            return;
        }

        pickerOpen = true;
        // WebView2 callbacks cannot synchronously enter a modal message loop.
        Dispatcher.BeginInvoke(new Action(() => PickDesign(requestId, source)));
    }

    private void PickDesign(string requestId, string source)
    {
        try
        {
            if (!IsAppOrigin(AppView.CoreWebView2.Source) || AppView.CoreWebView2.Source != source) return;
            var dialog = new OpenFileDialog
            {
                Title = "Kies een Rhino-ontwerp",
                Filter = "Rhino 3D-model (*.3dm)|*.3dm",
                DefaultExt = ".3dm",
                CheckFileExists = true,
                CheckPathExists = true,
                Multiselect = false,
                DereferenceLinks = true,
            };
            var selected = dialog.ShowDialog(this) == true;
            if (selected && !string.Equals(Path.GetExtension(dialog.FileName), ".3dm", StringComparison.OrdinalIgnoreCase))
            {
                SendPickerResult(requestId, "error", error: "Kies een Rhino .3dm-bestand.");
                return;
            }
            SendPickerResult(requestId, selected ? "selected" : "cancelled", selected ? dialog.FileName : null);
        }
        catch (Exception)
        {
            SendPickerResult(requestId, "error", error: "De bestandskiezer kon niet worden geopend. Probeer opnieuw.");
        }
        finally
        {
            pickerOpen = false;
        }
    }

    private void SendPickerResult(string requestId, string status, string? path = null, string? error = null)
    {
        if (!IsAppOrigin(AppView.CoreWebView2.Source)) return;
        AppView.CoreWebView2.PostWebMessageAsJson(JsonSerializer.Serialize(new
        {
            type = "parkhaven.pickDesignResult", requestId, status, path, error
        }));
    }

    protected override async void OnClosing(CancelEventArgs args)
    {
        base.OnClosing(args);
        if (shutdownComplete) return;
        args.Cancel = true;
        if (closing) return;
        closing = true;
        diagnosticsTimer.Stop();
        RetryStartup.Visibility = Visibility.Collapsed;
        ShowStatus("ParkHaven wordt afgesloten", "Eigen backend en Rhino-processen afsluiten...");
        lifetime.Cancel();
        await startup;
        foreach (var window in reportWindows.ToArray()) window.Close();
        if (backend != null) await backend.StopAsync();
        shutdownComplete = true;
        Close();
    }

    protected override void OnClosed(EventArgs args)
    {
        AppView.Dispose();
        diagnosticsClient.Dispose();
        lifetime.Dispose();
        base.OnClosed(args);
    }
}
