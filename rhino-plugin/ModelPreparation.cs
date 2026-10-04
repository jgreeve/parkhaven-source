using System.Drawing;
using System.Text.Json.Nodes;
using Rhino;
using Rhino.DocObjects;
using Rhino.FileIO;
using Rhino.Geometry;

namespace ParkHaven.Integration;

internal static class ModelPreparation
{
    private static readonly string[] ContextLayers = { "PH_FACADES", "PH_TARGET", "REFERENCE_CONTEXT" };

    private static int Layer(RhinoDoc doc, string name)
    {
        var index = doc.Layers.FindByFullPath(name, -1);
        return index >= 0 ? index : doc.Layers.Add(name, Color.White);
    }

    public static void Prepare(RhinoDoc doc, AnalysisJob job, bool requireAnalyticalVolumes = true)
    {
        job.SetStatus("preparing_model");
        job.BeginStep("classify_design", "Ontwerpobjecten controleren en plaatsen");
        if (doc.ModelUnitSystem is UnitSystem.None or UnitSystem.CustomUnits)
            throw new InvalidOperationException("Het model heeft geen ondersteunde fysieke eenheid.");
        var placement = job.Data["placement"]!;
        var requestedUnits = placement["model_units"]?.GetValue<string>() ?? "file";
        var effectiveUnits = requestedUnits switch
        {
            "file" => doc.ModelUnitSystem,
            "meters" => UnitSystem.Meters,
            "millimeters" => UnitSystem.Millimeters,
            "centimeters" => UnitSystem.Centimeters,
            _ => throw new InvalidDataException("Onbekende modeleenheid: " + requestedUnits)
        };
        // Interpret authored coordinates explicitly, then express them in the
        // document's declared units. Placement remains in physical metres.
        var coordinateScale = RhinoMath.UnitScale(effectiveUnits, doc.ModelUnitSystem);
        var inputBounds = BoundingBox.Empty;
        foreach (var obj in doc.Objects)
            if (!ContextLayers.Contains(doc.Layers[obj.Attributes.LayerIndex].Name))
                inputBounds.Union(obj.Geometry.GetBoundingBox(true));
        if (!inputBounds.IsValid) throw new InvalidDataException("Het ontwerp bevat geen meetbare geometrie.");
        var rawSize = inputBounds.Max - inputBounds.Min;
        var metersPerCoordinate = RhinoMath.UnitScale(effectiveUnits, UnitSystem.Meters);
        var originalTolerance = doc.ModelAbsoluteTolerance;
        if (coordinateScale != 1) doc.ModelAbsoluteTolerance = originalTolerance * coordinateScale;
        job.Data["model_units"] = new JsonObject
        {
            ["declared"] = doc.ModelUnitSystem.ToString(), ["interpreted"] = effectiveUnits.ToString(),
            ["coordinate_scale"] = coordinateScale,
            ["meters_per_coordinate"] = metersPerCoordinate,
            ["original_absolute_tolerance"] = originalTolerance,
            ["analysis_absolute_tolerance"] = doc.ModelAbsoluteTolerance,
            ["raw_size"] = new JsonArray(JsonValue.Create(rawSize.X), JsonValue.Create(rawSize.Y), JsonValue.Create(rawSize.Z)),
            ["physical_size_m"] = new JsonArray(JsonValue.Create(rawSize.X * metersPerCoordinate),
                JsonValue.Create(rawSize.Y * metersPerCoordinate), JsonValue.Create(rawSize.Z * metersPerCoordinate))
        };
        if (coordinateScale != 1)
            ((JsonArray)job.Data["warnings"]!).Add(JsonValue.Create(
                $"Modeleenheid gecorrigeerd: {doc.ModelUnitSystem} → {effectiveUnits}; coördinatenschaal {coordinateScale:G}. Bronbestand ongewijzigd."));
        else if (requestedUnits == "file" && Math.Max(rawSize.X, Math.Max(rawSize.Y, rawSize.Z)) * metersPerCoordinate < 1)
            ((JsonArray)job.Data["warnings"]!).Add(JsonValue.Create(
                "Het hele ontwerp is kleiner dan 1 meter. Controleer de modeleenheid bij Plaatsing; eenheden worden niet automatisch geraden."));
        job.Save();
        var translation = placement["translation_m"]!;
        double x = translation["x"]!.GetValue<double>(), y = translation["y"]!.GetValue<double>(),
            z = translation["z"]!.GetValue<double>(), angle = placement["rotation_z_degrees"]!.GetValue<double>();
        if (new[] { x, y, z, angle }.Any(value => !double.IsFinite(value)))
            throw new InvalidDataException("Plaatsing bevat ongeldige getallen.");
        var unitScale = RhinoMath.UnitScale(UnitSystem.Meters, doc.ModelUnitSystem);
        var transform = Transform.Translation(x * unitScale, y * unitScale, z * unitScale) *
            Transform.Rotation(RhinoMath.ToRadians(angle), Vector3d.ZAxis, Point3d.Origin) *
            Transform.Scale(Point3d.Origin, coordinateScale);
        var designLayer = Layer(doc, "PH_DESIGN");
        var visualLayer = Layer(doc, "PH_VISUAL_ONLY");
        int designCount = 0, visualCount = 0;
        var objects = doc.Objects.ToArray();
        job.Data["input_object_types"] = new JsonObject(objects.GroupBy(obj => obj.Geometry.GetType().Name)
            .Select(group => new KeyValuePair<string, JsonNode?>(group.Key, JsonValue.Create(group.Count()))));
        int processed = 0;
        foreach (var obj in objects)
        {
            processed++;
            // Reference masses must never be reclassified as proposed buildings.
            if (ContextLayers.Contains(doc.Layers[obj.Attributes.LayerIndex].Name)) continue;
            var geometry = obj.Geometry;
            var sourceObjectId = obj.Attributes.GetUserString(PreviewSceneExporter.SourceObjectIdKey) ?? obj.Id.ToString("D");
            job.ReportProgress($"Object {processed}/{objects.Length}: {geometry.GetType().Name} ({obj.Id}) controleren", objects.Length < 100);
            bool analytical = (geometry is Brep brep && brep.IsSolid || geometry is Extrusion extrusion && extrusion.IsSolid)
                && geometry.IsValid;
            if (obj.IsHidden || obj.IsLocked) analytical = false;
            // Move renderable design objects together, including visual-only geometry.
            var id = transform == Transform.Identity ? obj.Id : doc.Objects.Transform(obj.Id, transform, true);
            if (id == Guid.Empty)
                throw new InvalidOperationException("Een ontwerpobject kon niet worden geplaatst: " + obj.Id);
            var placed = doc.Objects.FindId(id);
            var attributes = placed.Attributes.Duplicate();
            job.ReportProgress($"Object {processed}/{objects.Length}: laag toewijzen ({obj.Id})", objects.Length < 100);
            attributes.LayerIndex = analytical ? designLayer : visualLayer;
            attributes.SetUserString(PreviewSceneExporter.SourceObjectIdKey, sourceObjectId);
            if (!doc.Objects.ModifyAttributes(placed, attributes, true))
                throw new InvalidOperationException("Objectclassificatie kon niet worden opgeslagen.");
            if (analytical) designCount++; else visualCount++;
        }
        if (requireAnalyticalVolumes && designCount == 0)
            throw new InvalidOperationException("Geen geldige gesloten Breps of extrusies gevonden voor PH_DESIGN.");

        job.BeginStep("read_context", "Parkhaven-referentiemodel lezen");
        using var context = File3dm.Read(job.Text("context_model"))
            ?? throw new InvalidDataException("Parkhaven-referentiemodel kon niet worden gelezen.");
        var scale = Transform.Scale(Point3d.Origin, RhinoMath.UnitScale(context.Settings.ModelUnitSystem, doc.ModelUnitSystem));
        job.Data["preparation_units"] = new JsonObject { ["design"] = doc.ModelUnitSystem.ToString(),
            ["context"] = context.Settings.ModelUnitSystem.ToString() };
        var counts = new JsonObject();
        foreach (var name in ContextLayers)
        {
            job.BeginStep("context_" + name, "Referentielaag vervangen: " + name);
            var layerIndex = Layer(doc, name);
            foreach (var obj in doc.Objects.FindByLayer(doc.Layers[layerIndex]))
                if (!doc.Objects.Delete(obj, true))
                    throw new InvalidOperationException("Bestaande referentie kon niet worden vervangen: " + name);
            int count = 0;
            foreach (var obj in context.Objects)
            {
                if (context.AllLayers.FindIndex(obj.Attributes.LayerIndex)?.Name != name) continue;
                job.ReportProgress($"{name}: object {count + 1}, {obj.Geometry.GetType().Name} invoegen ({obj.Id})");
                using var geometry = obj.Geometry.Duplicate();
                if (!geometry.Transform(scale)) throw new InvalidOperationException("Referentie-eenheden konden niet worden omgerekend.");
                var attributes = obj.Attributes.Duplicate();
                attributes.LayerIndex = layerIndex;
                attributes.SetUserString(PreviewSceneExporter.SourceObjectIdKey, obj.Id.ToString("D"));
                if (doc.Objects.Add(geometry, attributes) == Guid.Empty)
                    throw new InvalidOperationException("Referentieobject kon niet worden toegevoegd.");
                count++;
            }
            job.ReportProgress($"{name}: {count} objecten toegevoegd", true);
            if (count == 0 && name != "REFERENCE_CONTEXT")
                throw new InvalidDataException("Verplichte referentielaag is leeg: " + name);
            counts[name] = count;
        }
        job.BeginStep("summarize_model", "Modelsamenvatting vastleggen");
        job.Data["model_summary"] = new JsonObject
        {
            ["design_objects"] = designCount, ["visual_only_objects"] = visualCount,
            ["context_objects"] = counts, ["units"] = doc.ModelUnitSystem.ToString()
        };
        if (visualCount > 0)
            ((JsonArray)job.Data["warnings"]!).Add(JsonValue.Create($"{visualCount} objecten zijn alleen visueel; niet meegenomen als analysevolume."));
        job.Save();
        job.BeginStep("redraw", "Rhino-weergave bijwerken");
        doc.Views.Redraw();
    }
}
