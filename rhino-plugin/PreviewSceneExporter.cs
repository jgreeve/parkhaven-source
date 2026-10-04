using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Rhino;
using Rhino.DocObjects;
using Rhino.Geometry;

namespace ParkHaven.Integration;

internal static class PreviewSceneExporter
{
    internal const string SourceObjectIdKey = "ParkHaven.SourceObjectId";
    private const int SummaryObjectLimit = 5000;
    private static readonly string[] SceneLayerNames =
    {
        "PH_DESIGN", "PH_VISUAL_ONLY", "PH_FACADES", "PH_TARGET", "REFERENCE_CONTEXT"
    };
    private static readonly HashSet<string> EvidenceLayers = new() { "PH_DESIGN", "PH_VISUAL_ONLY" };

    public static void Export(RhinoDoc doc, AnalysisJob job, bool writePreviewScene)
    {
        job.BeginStep("export_geometry_evidence", writePreviewScene
            ? "3D-preview en objectbewijs opbouwen" : "Objectbewijs voor analyse vastleggen");
        var unitScale = RhinoMath.UnitScale(doc.ModelUnitSystem, UnitSystem.Meters);
        var scene = writePreviewScene
            ? new StringBuilder("{\"schema_version\":1,\"kind\":\"placement_preview\",\"units\":\"meters\",\"up_axis\":\"Z\",\"layers\":[")
            : null;
        var layerSummary = new JsonObject();
        var evidenceObjects = new List<JsonObject>();
        var omittedTypes = new Dictionary<string, int>();
        var seenIds = new HashSet<string>(StringComparer.Ordinal);
        var totalEvidenceObjects = 0;
        var mappingOmitted = 0;
        var layers = writePreviewScene ? SceneLayerNames : EvidenceLayers.ToArray();

        for (var layerNumber = 0; layerNumber < layers.Length; layerNumber++)
        {
            var name = layers[layerNumber];
            if (scene != null && layerNumber > 0) scene.Append(',');
            using var combined = new Mesh();
            var mappings = new JsonArray();
            var meshedObjectCount = 0;
            var layerIndex = doc.Layers.FindByFullPath(name, -1);
            var objects = layerIndex < 0 ? Array.Empty<RhinoObject>() : doc.Objects.FindByLayer(doc.Layers[layerIndex])
                .OrderBy(StableId, StringComparer.Ordinal).ToArray();
            for (var index = 0; index < objects.Length; index++)
            {
                var obj = objects[index];
                job.ReportProgress($"{name}: object {index + 1}/{objects.Length} exporteren");
                var id = StableId(obj);
                if (!seenIds.Add(id) && EvidenceLayers.Contains(name))
                    throw new InvalidDataException("Dubbel stabiel object-ID in geometriebewijs: " + id);
                using var objectMesh = MeshGeometry(obj.Geometry);
                var vertexStart = combined.Vertices.Count;
                var triangleStart = combined.Faces.Count;
                var meshAvailable = objectMesh != null;
                if (objectMesh != null)
                {
                    objectMesh.Faces.ConvertQuadsToTriangles();
                    objectMesh.Compact();
                    combined.Append(objectMesh);
                    meshedObjectCount++;
                }
                else
                {
                    var type = obj.Geometry.GetType().Name;
                    omittedTypes[type] = omittedTypes.GetValueOrDefault(type) + 1;
                }

                if (!EvidenceLayers.Contains(name)) continue;
                totalEvidenceObjects++;
                if (evidenceObjects.Count >= SummaryObjectLimit)
                {
                    mappingOmitted++;
                    continue;
                }
                var vertexCount = combined.Vertices.Count - vertexStart;
                var triangleCount = combined.Faces.Count - triangleStart;
                var mapping = new JsonObject
                {
                    ["id"] = id, ["vertex_start"] = vertexStart, ["vertex_count"] = vertexCount,
                    ["triangle_start"] = triangleStart, ["triangle_count"] = triangleCount
                };
                mappings.Add(Clone(mapping));
                evidenceObjects.Add(ObjectSummary(obj, id, name, unitScale, meshAvailable, vertexCount, triangleCount));
            }
            combined.Faces.ConvertQuadsToTriangles();
            combined.Compact();
            if (scene != null) AppendLayer(scene, name, combined, unitScale, mappings);
            layerSummary[name] = new JsonObject
            {
                ["objects"] = meshedObjectCount,
                ["vertices"] = combined.Vertices.Count,
                ["triangles"] = combined.Faces.Count,
                ["mapped_objects"] = mappings.Count
            };
        }
        if (scene != null) scene.Append("]}");

        if (omittedTypes.Count > 0 && writePreviewScene)
        {
            var detail = string.Join(", ", omittedTypes.OrderBy(item => item.Key).Select(item => $"{item.Key}: {item.Value}"));
            ((JsonArray)job.Data["warnings"]!).Add(JsonValue.Create(
                "Niet-ondersteunde objecten ontbreken in de previewmesh (" + detail + ")."));
        }
        if (mappingOmitted > 0)
            ((JsonArray)job.Data["warnings"]!).Add(JsonValue.Create(
                $"Geometriesamenvatting begrensd op {SummaryObjectLimit} objecten; {mappingOmitted} objecten niet samengevat."));

        var dataDirectory = job.Text("data_dir");
        Directory.CreateDirectory(dataDirectory);
        var summaryPath = Path.Combine(dataDirectory, "geometry-summary.json");
        var objectsNode = new JsonArray(evidenceObjects.Select(item => (JsonNode?)item).ToArray());
        var objectsSha256 = Sha256Text(objectsNode.ToJsonString());
        var summary = new JsonObject
        {
            ["schema_version"] = 1,
            ["id_strategy"] = "source-rhino-object-uuid-v1",
            ["units"] = "meters",
            ["up_axis"] = "Z",
            ["job_type"] = job.JobType,
            ["project_id"] = job.Text("project_id"),
            ["run_id"] = job.Text("run_id"),
            ["source_sha256"] = job.Text("source_sha256"),
            ["input_sha256"] = job.Text("input_sha256"),
            ["context_sha256"] = job.Text("context_sha256"),
            ["placement"] = Clone(job.Data["placement"]),
            ["object_limit"] = SummaryObjectLimit,
            ["total_objects"] = totalEvidenceObjects,
            ["included_objects"] = evidenceObjects.Count,
            ["omitted_objects"] = mappingOmitted,
            ["objects_sha256"] = objectsSha256,
            ["objects"] = objectsNode
        };
        WriteAtomic(summaryPath, summary.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
        job.Data["geometry_summary"] = new JsonObject
        {
            ["schema_version"] = 1,
            ["sha256"] = Sha256(summaryPath),
            ["objects_sha256"] = objectsSha256,
            ["total_objects"] = totalEvidenceObjects,
            ["included_objects"] = evidenceObjects.Count,
            ["omitted_objects"] = mappingOmitted
        };

        if (scene != null)
        {
            var scenePath = Path.Combine(dataDirectory, "scene.json");
            WriteAtomic(scenePath, scene.ToString());
            job.Data["preview_scene"] = new JsonObject
            {
                ["schema_version"] = 1,
                ["sha256"] = Sha256(scenePath),
                ["omitted_objects"] = omittedTypes.Values.Sum(),
                ["mapping_omitted_objects"] = mappingOmitted,
                ["layers"] = layerSummary
            };
        }
        job.Save();
    }

    private static string StableId(RhinoObject obj)
    {
        var text = obj.Attributes.GetUserString(SourceObjectIdKey) ?? obj.Id.ToString("D");
        if (!Guid.TryParse(text, out var id)) throw new InvalidDataException("Ongeldig bronobject-ID: " + text);
        return "source:" + id.ToString("D").ToLowerInvariant();
    }

    private static JsonObject ObjectSummary(RhinoObject obj, string id, string layer, double unitScale,
        bool meshAvailable, int vertexCount, int triangleCount)
    {
        var bounds = obj.Geometry.GetBoundingBox(true);
        if (!bounds.IsValid) throw new InvalidDataException("Object heeft geen geldige begrenzing: " + id);
        var min = bounds.Min * unitScale;
        var max = bounds.Max * unitScale;
        var size = max - min;
        return new JsonObject
        {
            ["id"] = id,
            ["source_object_uuid"] = id["source:".Length..],
            ["layer"] = layer,
            ["classification"] = layer == "PH_DESIGN" ? "analysis_volume" : "visual_only",
            ["geometry_type"] = obj.Geometry.GetType().Name,
            ["mesh_available"] = meshAvailable,
            ["bounds_m"] = new JsonObject
            {
                ["min"] = Coordinates(min), ["max"] = Coordinates(max)
            },
            ["dimensions_m"] = Coordinates(size),
            ["height_m"] = size.Z,
            ["vertex_count"] = vertexCount,
            ["triangle_count"] = triangleCount
        };
    }

    private static JsonArray Coordinates(Point3d point) => new(JsonValue.Create(point.X), JsonValue.Create(point.Y), JsonValue.Create(point.Z));
    private static JsonArray Coordinates(Vector3d vector) => new(JsonValue.Create(vector.X), JsonValue.Create(vector.Y), JsonValue.Create(vector.Z));
    private static JsonNode? Clone(JsonNode? node) => node == null ? null : JsonNode.Parse(node.ToJsonString());

    private static Mesh? MeshGeometry(GeometryBase geometry)
    {
        if (geometry is Mesh mesh) return mesh.DuplicateMesh();
        Brep? brep = geometry as Brep;
        var ownsBrep = false;
        if (geometry is Extrusion extrusion)
        {
            brep = extrusion.ToBrep();
            ownsBrep = true;
        }
        if (brep == null) return null;
        try
        {
            var pieces = Mesh.CreateFromBrep(brep, MeshingParameters.FastRenderMesh);
            if (pieces == null) return null;
            var combined = new Mesh();
            foreach (var piece in pieces)
            {
                combined.Append(piece);
                piece.Dispose();
            }
            return combined;
        }
        finally
        {
            if (ownsBrep) brep.Dispose();
        }
    }

    private static void AppendLayer(StringBuilder json, string name, Mesh mesh, double unitScale, JsonArray mappings)
    {
        json.Append("{\"name\":\"").Append(name).Append("\",\"vertices\":[");
        for (var index = 0; index < mesh.Vertices.Count; index++)
        {
            if (index > 0) json.Append(',');
            var point = mesh.Vertices[index];
            Coordinate(json, point.X * unitScale); json.Append(',');
            Coordinate(json, point.Y * unitScale); json.Append(',');
            Coordinate(json, point.Z * unitScale);
        }
        json.Append("],\"triangles\":[");
        for (var index = 0; index < mesh.Faces.Count; index++)
        {
            if (index > 0) json.Append(',');
            var face = mesh.Faces[index];
            json.Append(face.A).Append(',').Append(face.B).Append(',').Append(face.C);
        }
        json.Append("],\"objects\":").Append(mappings.ToJsonString()).Append('}');
    }

    private static void Coordinate(StringBuilder json, double number)
    {
        if (!double.IsFinite(number)) throw new InvalidDataException("Geometriebewijs bevat een ongeldige meshcoordinaat.");
        json.Append(number.ToString("0.######", CultureInfo.InvariantCulture));
    }

    private static void WriteAtomic(string path, string contents)
    {
        var temporary = path + ".tmp";
        try
        {
            File.WriteAllText(temporary, contents, new UTF8Encoding(false));
            for (var attempt = 0; ; attempt++)
            {
                try { File.Move(temporary, path, true); break; }
                catch (Exception ex) when (attempt < 5 && ex is IOException or UnauthorizedAccessException)
                { Thread.Sleep(25 * (attempt + 1)); }
            }
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    private static string Sha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static string Sha256Text(string text) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text))).ToLowerInvariant();
}
