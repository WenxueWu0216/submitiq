using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace SubmitIQ.Api.Services;

/// <summary>
/// Reads and writes one scalar in the pipeline's record JSON by flattened path, using the same
/// keys as submitiq/fields.py: locations by loc_number, claims by normalized claim number,
/// loss_years by policy_year, e.g. "locations[3].year_built", "claims[CMI202312345].paid".
/// </summary>
public static partial class RecordPaths
{
    [GeneratedRegex(@"^(?<group>[a-z_]+)(?:\[(?<key>[^\]]+)\])?\.(?<rest>[a-z_.]+)$")]
    private static partial Regex PathPattern();

    [GeneratedRegex("[^A-Z0-9]")]
    private static partial Regex NonAlnum();

    public static string ClaimKey(string claimNumber) => NonAlnum().Replace(claimNumber.ToUpperInvariant(), "");

    public static JsonNode? Get(JsonObject record, string path)
    {
        var (parent, leaf) = Locate(record, path, create: false);
        return parent?[leaf];
    }

    /// <summary>Sets the value; returns false if the path does not address an existing object.</summary>
    public static bool Set(JsonObject record, string path, JsonNode? value)
    {
        var (parent, leaf) = Locate(record, path, create: true);
        if (parent is null)
            return false;
        parent[leaf] = value;
        return true;
    }

    private static (JsonObject? Parent, string Leaf) Locate(JsonObject record, string path, bool create)
    {
        var m = PathPattern().Match(path);
        if (!m.Success)
            return (null, "");
        var group = m.Groups["group"].Value;
        var rest = m.Groups["rest"].Value.Split('.');
        JsonObject? current;
        if (m.Groups["key"].Success)
        {
            var key = m.Groups["key"].Value;
            if (record[group] is not JsonArray items)
                return (null, "");
            current = group switch
            {
                "locations" => items.OfType<JsonObject>().FirstOrDefault(o => o["loc_number"]?.ToString() == key),
                "claims" => items.OfType<JsonObject>().FirstOrDefault(o => ClaimKey(o["claim_number"]?.ToString() ?? "") == key),
                "loss_years" => items.OfType<JsonObject>().FirstOrDefault(o => o["policy_year"]?.ToString() == key),
                _ => null,
            };
        }
        else
        {
            current = record[group] as JsonObject;
            if (current is null && create && group is "insured" or "broker" or "policy" or "coverage" or "totals")
            {
                current = new JsonObject();
                record[group] = current;
            }
        }
        for (var i = 0; current is not null && i < rest.Length - 1; i++)
        {
            var next = current[rest[i]] as JsonObject;
            if (next is null && create)
            {
                next = new JsonObject();
                current[rest[i]] = next;
            }
            current = next;
        }
        return (current, rest[^1]);
    }
}
