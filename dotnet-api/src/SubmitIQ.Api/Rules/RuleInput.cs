using System.Text.Json;
using System.Text.Json.Nodes;

namespace SubmitIQ.Api.Rules;

/// <summary>
/// The slice of a submission record the appetite rules read. Deserialized from the pipeline's
/// record JSON (same shape as submitiq.schema.Submission); unknown fields are ignored.
/// </summary>
public sealed class RuleInput
{
    public InsuredPart Insured { get; set; } = new();
    public PolicyPart Policy { get; set; } = new();
    public TotalsPart Totals { get; set; } = new();
    public List<LocationPart> Locations { get; set; } = [];
    public List<ClaimPart> Claims { get; set; } = [];
    public List<LossYearPart> LossYears { get; set; } = [];

    private static readonly JsonSerializerOptions Options = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };

    public static RuleInput From(JsonObject record) => record.Deserialize<RuleInput>(Options) ?? new RuleInput();

    public static RuleInput From(string recordJson) => JsonSerializer.Deserialize<RuleInput>(recordJson, Options) ?? new RuleInput();
}

public sealed class InsuredPart
{
    public string? NaicsCode { get; set; }
}

public sealed class PolicyPart
{
    public DateOnly? EffectiveDate { get; set; }
}

public sealed class TotalsPart
{
    public double? TotalTiv { get; set; }
}

public sealed class LocationPart
{
    public int LocNumber { get; set; }
    public string? Zip { get; set; }
    public string? Construction { get; set; }
    public int? YearBuilt { get; set; }
    public int? ProtectionClass { get; set; }
    public bool? Sprinklered { get; set; }
    public int? RoofYear { get; set; }
    public double? Tiv { get; set; }

    /// <summary>The value of a required location field named in appetite.yaml (null = missing).</summary>
    public object? Required(string field) => field switch
    {
        "construction" => Construction,
        "year_built" => YearBuilt,
        "protection_class" => ProtectionClass,
        "tiv" => Tiv,
        "zip" => Zip,
        "sprinklered" => Sprinklered,
        "roof_year" => RoofYear,
        _ => throw new InvalidOperationException($"appetite.yaml requires location field '{field}', which the rules engine does not read"),
    };
}

public sealed class ClaimPart
{
    public string ClaimNumber { get; set; } = "";
    public string? Cause { get; set; }
    public double? Incurred { get; set; }
}

public sealed class LossYearPart
{
    public int PolicyYear { get; set; }
    public double? EarnedPremium { get; set; }
}
