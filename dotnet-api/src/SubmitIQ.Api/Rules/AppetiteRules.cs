using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace SubmitIQ.Api.Rules;

/// <summary>
/// rules/appetite.yaml, deserialized as-is. The Python engine (submitiq/rules_engine.py) reads the
/// same file; no threshold or class list is restated in C#.
/// </summary>
public sealed class AppetiteRules
{
    public string Version { get; set; } = "";
    public List<string> OutcomeOrder { get; set; } = [];
    public ClassLists Classes { get; set; } = new();
    public TivRules Tiv { get; set; } = new();
    public LossRules Losses { get; set; } = new();
    public ConstructionProtectionRules ConstructionProtection { get; set; } = new();
    public CatZoneRules CatZones { get; set; } = new();
    public SprinklerRules Sprinklers { get; set; } = new();
    public AgeRules Age { get; set; } = new();
    public RequiredFields RequiredFields { get; set; } = new();

    public static AppetiteRules Load(string path)
    {
        var rules = new DeserializerBuilder()
            .WithNamingConvention(UnderscoredNamingConvention.Instance)
            .Build()
            .Deserialize<AppetiteRules>(File.ReadAllText(path));
        if (string.IsNullOrEmpty(rules.Version) || rules.Classes.Accept.Count == 0)
            throw new InvalidOperationException($"{path} is not a valid appetite rules file");
        return rules;
    }
}

public sealed class ClassLists
{
    // NAICS code -> occupancy label
    public Dictionary<string, string> Accept { get; set; } = [];
    public Dictionary<string, string> Refer { get; set; } = [];
    public Dictionary<string, string> Decline { get; set; } = [];
}

public sealed class TivRules
{
    public double LocationReferAbove { get; set; }
    public double LocationDeclineAbove { get; set; }
    public double AccountReferAbove { get; set; }
}

public sealed class LossRules
{
    public double LossRatioReferAbove { get; set; }
    public double LossRatioDeclineAbove { get; set; }
    public int ClaimCountReferAtOrAbove { get; set; }
    public double LargeLossReferAbove { get; set; }
}

public sealed class ConstructionProtectionRules
{
    [YamlMember(Alias = "decline_frame_with_pc_at_or_above")]
    public int DeclineFrameWithPcAtOrAbove { get; set; }

    [YamlMember(Alias = "refer_pc_at_or_above")]
    public int ReferPcAtOrAbove { get; set; }
}

public sealed class CatZoneRules
{
    [YamlMember(Alias = "hurricane_tier1_zip3")]
    public List<string> HurricaneTier1Zip3 { get; set; } = [];

    public double HurricaneReferLocationTivAbove { get; set; }

    [YamlMember(Alias = "earthquake_zip3")]
    public List<string> EarthquakeZip3 { get; set; } = [];

    public int EarthquakeReferJmBuiltBefore { get; set; }
}

public sealed class SprinklerRules
{
    public double ReferUnsprinkleredLocationTivAbove { get; set; }
}

public sealed class AgeRules
{
    public int ReferYearBuiltBefore { get; set; }
    public int ReferRoofAgeOverYears { get; set; }
}

public sealed class RequiredFields
{
    public List<string> Account { get; set; } = [];
    public List<string> Location { get; set; } = [];
}
