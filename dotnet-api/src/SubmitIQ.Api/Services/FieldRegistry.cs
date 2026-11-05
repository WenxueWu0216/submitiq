using System.Text.Json;
using System.Text.RegularExpressions;

namespace SubmitIQ.Api.Services;

public sealed record FieldSpec(string Group, string Kind, bool Critical);

/// <summary>
/// Field kinds and critical flags, read from contracts/field_registry.json, which is exported from
/// the Python registry (submitiq/fields.py) by scripts/export_contracts.py. Never edited by hand.
/// </summary>
public sealed partial class FieldRegistry
{
    private readonly Dictionary<string, FieldSpec> _specs;

    public FieldRegistry(Dictionary<string, FieldSpec> specs) => _specs = specs;

    public static FieldRegistry Load(string path)
    {
        var raw = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(File.ReadAllText(path))
                  ?? throw new InvalidOperationException($"empty field registry {path}");
        return new FieldRegistry(raw.ToDictionary(
            kv => kv.Key,
            kv => new FieldSpec(kv.Value.GetProperty("group").GetString()!, kv.Value.GetProperty("kind").GetString()!,
                                kv.Value.GetProperty("critical").GetBoolean())));
    }

    [GeneratedRegex(@"\[[^\]]*\]")]
    private static partial Regex IndexPattern();

    /// <summary>locations[3].year_built -> locations[].year_built</summary>
    public static string Generic(string path) => IndexPattern().Replace(path, "[]");

    public FieldSpec? Find(string path) => _specs.GetValueOrDefault(Generic(path));

    public int Count => _specs.Count;
}
