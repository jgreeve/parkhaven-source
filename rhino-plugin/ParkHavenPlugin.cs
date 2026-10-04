using System.Runtime.InteropServices;
using Rhino;
using Rhino.Commands;
using Rhino.PlugIns;

[assembly: Guid("7ff947f5-d80c-4be6-bc9b-88f77bdfe605")]

namespace ParkHaven.Integration;

public sealed class ParkHavenPlugin : PlugIn
{
    public override PlugInLoadTime LoadTime => PlugInLoadTime.AtStartup;

    protected override LoadReturnCode OnLoad(ref string errorMessage)
    {
        // Only app-owned processes receive a job. Normal Rhino sessions stay idle.
        if (!string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("PARKHAVEN_JOB_FILE")))
            RhinoApp.Idle += DispatchJob;
        return LoadReturnCode.Success;
    }

    private void DispatchJob(object? sender, EventArgs args)
    {
        var doc = RhinoDoc.ActiveDoc;
        if (doc == null || RhinoApp.InCommand != 0) return;
        var path = Environment.GetEnvironmentVariable("PARKHAVEN_JOB_FILE")!;
        try
        {
            var job = AnalysisJob.Read(path);
            // Startup can idle before the command-line model has finished opening.
            if (!job.MatchesDocument(doc)) return;
            RhinoApp.Idle -= DispatchJob;
            RhinoApp.RunScript("_ParkHavenAnalyze", false);
        }
        catch (Exception ex)
        {
            RhinoApp.Idle -= DispatchJob;
            RhinoApp.WriteLine("ParkHaven: " + ex.Message);
        }
    }

    protected override void OnShutdown() => RhinoApp.Idle -= DispatchJob;
}

[CommandStyle(Style.ScriptRunner)]
public sealed class ParkHavenAnalyzeCommand : Command
{
    public override string EnglishName => "ParkHavenAnalyze";

    protected override Result RunCommand(RhinoDoc doc, RunMode mode)
    {
        var path = Environment.GetEnvironmentVariable("PARKHAVEN_JOB_FILE");
        if (string.IsNullOrWhiteSpace(path))
        {
            RhinoApp.WriteLine("Start deze Rhino-sessie vanuit de ParkHaven-app.");
            return Result.Failure;
        }
        AnalysisJob? job = null;
        try
        {
            // File locking also rejects a second Rhino process consuming this job.
            using var lease = new FileStream(Path.Combine(Path.GetDirectoryName(path)!, "runner.lock"),
                FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
            job = AnalysisJob.Read(path);
            if (job.Status is not ("prepared" or "launch_requested"))
                throw new InvalidOperationException("Deze run is al gestart. Maak een nieuwe analyse aan.");
            if (!job.MatchesDocument(doc))
                throw new InvalidOperationException("Het actieve Rhino-document is niet de geisoleerde runkopie.");
            job.SetStatus("runner_started");
            job.RecordRuntime();
            ModelPreparation.Prepare(doc, job, !job.IsPlacementPreview);
            PreviewSceneExporter.Export(doc, job, job.IsPlacementPreview);
            if (job.IsPlacementPreview)
            {
                job.BeginStep("finished", "Plaatsingspreview voltooid");
                job.SetStatus("completed");
                RhinoApp.WriteLine("ParkHaven: plaatsingspreview voltooid.");
                return Result.Success;
            }
            job.BeginStep("load_grasshopper", "Grasshopper starten");
            if (!RhinoApp.RunScript("_Grasshopper", false))
                throw new InvalidOperationException("Grasshopper kon niet worden gestart.");
            GrasshopperSolver.Solve(job);
            job.BeginStep("finished", "Analyse voltooid");
            job.SetStatus("completed");
            RhinoApp.WriteLine("ParkHaven: analyse voltooid.");
            return Result.Success;
        }
        catch (Exception ex)
        {
            // Preserve the original error even if publishing job.json itself fails.
            LogFailure(path, ex);
            RhinoApp.WriteLine("ParkHaven: " + ex.Message);
            if (job != null && job.Status is "runner_started" or "preparing_model" or "solving")
            {
                try { job.Fail(ex); }
                catch (Exception publicationError)
                {
                    LogFailure(path, publicationError);
                    RhinoApp.WriteLine("ParkHaven: foutstatus kon niet worden opgeslagen: " + publicationError.Message);
                }
            }
            return Result.Failure;
        }
    }

    private static void LogFailure(string jobPath, Exception error)
    {
        try { File.AppendAllText(Path.Combine(Path.GetDirectoryName(jobPath)!, "runner-error.log"),
            DateTime.UtcNow.ToString("O") + " " + error + Environment.NewLine); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        { RhinoApp.WriteLine("ParkHaven: foutlog kon niet worden opgeslagen: " + ex.Message); }
    }
}
