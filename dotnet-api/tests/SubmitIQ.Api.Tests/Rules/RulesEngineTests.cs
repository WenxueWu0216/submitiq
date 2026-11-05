using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Rules;
using SubmitIQ.Api.Tests.Infrastructure;

namespace SubmitIQ.Api.Tests.Rules;

/// <summary>Rule-by-rule unit tests, mirroring tests/test_rules_engine.py on the Python side.</summary>
public class RulesEngineTests
{
    private static readonly AppetiteRules Yaml = AppetiteRules.Load(RepoPaths.AppetiteYaml);
    private static readonly RulesEngine Engine = new(Yaml);

    /// <summary>A risk that triggers no rule; each test changes one thing.</summary>
    private static RuleInput Clean(Action<LocationPart>? loc = null)
    {
        var l = new LocationPart
        {
            LocNumber = 1, Zip = "43215", Construction = "masonry_non_combustible", YearBuilt = 1995, ProtectionClass = 3,
            Sprinklered = true, RoofYear = 2020, Tiv = 2_000_000,
        };
        loc?.Invoke(l);
        return new RuleInput
        {
            Insured = new InsuredPart { NaicsCode = "493110" },
            Policy = new PolicyPart { EffectiveDate = new DateOnly(2027, 1, 1) },
            Totals = new TotalsPart { TotalTiv = l.Tiv },
            Locations = [l],
            LossYears = Enumerable.Range(2022, 5).Select(y => new LossYearPart { PolicyYear = y, EarnedPremium = 10_000 }).ToList(),
        };
    }

    /// <summary>Outcome plus the distinct rule IDs, sorted and comma-joined (tuples of strings compare by value).</summary>
    private static (DecisionOutcome Outcome, string Rules) Run(RuleInput rec)
    {
        var r = Engine.Evaluate(rec);
        return (r.Outcome, string.Join(",", r.Reasons.Select(x => x.RuleId).Distinct().Order(StringComparer.Ordinal)));
    }

    [Fact]
    public void Clean_risk_is_accepted_with_no_reasons()
    {
        var r = Engine.Evaluate(Clean());
        Assert.Equal(DecisionOutcome.Accept, r.Outcome);
        Assert.Empty(r.Reasons);
        Assert.Equal("2026-10-01", r.RulesVersion);
    }

    [Theory]
    [InlineData("325920", DecisionOutcome.Decline, "CLASS_PROHIBITED")]
    [InlineData("721110", DecisionOutcome.Refer, "CLASS_REFER")]
    [InlineData("999999", DecisionOutcome.Refer, "CLASS_UNKNOWN")]
    [InlineData(null, DecisionOutcome.Refer, "MISSING_INFO")]
    public void Class_rules(string? naics, DecisionOutcome expected, string rule)
    {
        var rec = Clean();
        rec.Insured.NaicsCode = naics;
        Assert.Equal((expected, rule), Run(rec));
    }

    [Fact]
    public void Missing_required_location_fields_refer_and_name_each_field()
    {
        var r = Engine.Evaluate(Clean(l => { l.ProtectionClass = null; l.YearBuilt = null; }));
        var hit = Assert.Single(r.Reasons);
        Assert.Equal(("MISSING_INFO", DecisionOutcome.Refer), (hit.RuleId, hit.Outcome));
        Assert.Equal(["locations[1].year_built", "locations[1].protection_class"], hit.Fields);   // YAML order
        Assert.Equal("location 1: missing year_built, protection_class", hit.Message);
    }

    [Fact]
    public void Frame_with_poor_protection_declines_and_pc10_also_refers()
    {
        Assert.Equal((DecisionOutcome.Decline, "FRAME_POOR_PROTECTION"), Run(Clean(l => { l.Construction = "frame"; l.ProtectionClass = 9; })));
        Assert.Equal((DecisionOutcome.Accept, ""), Run(Clean(l => { l.Construction = "frame"; l.ProtectionClass = 8; })));
        Assert.Equal((DecisionOutcome.Decline, "FRAME_POOR_PROTECTION,POOR_PROTECTION"),
                     Run(Clean(l => { l.Construction = "frame"; l.ProtectionClass = 10; })));
        Assert.Equal((DecisionOutcome.Refer, "POOR_PROTECTION"), Run(Clean(l => l.ProtectionClass = 10)));
    }

    [Fact]
    public void Hurricane_zone_declines_frame_and_refers_large_values()
    {
        Assert.Equal(DecisionOutcome.Decline, Run(Clean(l => { l.Zip = "33101"; l.Construction = "frame"; l.ProtectionClass = 4; })).Outcome);
        Assert.Equal((DecisionOutcome.Refer, "HURRICANE_ZONE"), Run(Clean(l => { l.Zip = "33101"; l.Tiv = 6_000_000; })));
        Assert.Equal(DecisionOutcome.Accept, Run(Clean(l => { l.Zip = "33101"; l.Tiv = 4_000_000; })).Outcome);
        // A frame building gets the decline hit only, never a second refer hit for the same zone.
        var r = Engine.Evaluate(Clean(l => { l.Zip = "33101"; l.Construction = "frame"; l.Tiv = 6_000_000; }));
        Assert.Single(r.Reasons, h => h.RuleId == "HURRICANE_ZONE");
    }

    [Fact]
    public void Earthquake_zone_refers_old_joisted_masonry_only()
    {
        Assert.Equal((DecisionOutcome.Refer, "EARTHQUAKE_ZONE"),
                     Run(Clean(l => { l.Zip = "94110"; l.Construction = "joisted_masonry"; l.YearBuilt = 1975; })));
        Assert.Equal(DecisionOutcome.Accept, Run(Clean(l => { l.Zip = "94110"; l.Construction = "joisted_masonry"; l.YearBuilt = 1980; })).Outcome);
        Assert.Equal(DecisionOutcome.Accept, Run(Clean(l => { l.Zip = "94110"; l.YearBuilt = 1975; })).Outcome);
    }

    [Theory]
    [InlineData(25_000_000.0, DecisionOutcome.Accept)]    // strictly greater than: exactly $25M is not referred
    [InlineData(25_000_001.0, DecisionOutcome.Refer)]
    [InlineData(50_000_000.0, DecisionOutcome.Refer)]
    [InlineData(50_000_001.0, DecisionOutcome.Decline)]
    public void Location_tiv_thresholds_are_strict(double tiv, DecisionOutcome expected)
    {
        Assert.Equal(expected, Run(Clean(l => l.Tiv = tiv)).Outcome);
    }

    [Fact]
    public void Account_tiv_above_limit_refers()
    {
        var rec = Clean();
        rec.Totals.TotalTiv = 100_000_001;
        Assert.Equal((DecisionOutcome.Refer, "ACCOUNT_TIV"), Run(rec));
    }

    [Fact]
    public void Unsprinklered_large_location_refers()
    {
        Assert.Equal((DecisionOutcome.Refer, "UNSPRINKLERED"), Run(Clean(l => { l.Sprinklered = false; l.Tiv = 12_000_000; })));
        Assert.Equal(DecisionOutcome.Accept, Run(Clean(l => { l.Sprinklered = null; l.Tiv = 12_000_000; })).Outcome);   // unknown is not "false"
    }

    [Fact]
    public void Building_and_roof_age()
    {
        Assert.Equal((DecisionOutcome.Refer, "BUILDING_AGE"), Run(Clean(l => l.YearBuilt = 1949)));
        Assert.Equal(DecisionOutcome.Accept, Run(Clean(l => l.YearBuilt = 1950)).Outcome);
        Assert.Equal((DecisionOutcome.Refer, "ROOF_AGE"), Run(Clean(l => l.RoofYear = 2001)));   // 26 years at 2027
        Assert.Equal(DecisionOutcome.Accept, Run(Clean(l => l.RoofYear = 2002)).Outcome);                  // exactly 25
    }

    private static RuleInput WithClaims(params double[] incurred)
    {
        var rec = Clean();
        rec.Claims = incurred.Select((x, i) => new ClaimPart { ClaimNumber = $"C-{i}", Incurred = x }).ToList();
        return rec;
    }

    [Fact]
    public void Loss_ratio_thresholds_against_fifty_thousand_premium()
    {
        Assert.Equal(DecisionOutcome.Accept, Run(WithClaims(30_000)).Outcome);                      // exactly 60%
        Assert.Equal((DecisionOutcome.Refer, "LOSS_RATIO"), Run(WithClaims(30_001)));
        Assert.Equal((DecisionOutcome.Decline, "LOSS_RATIO"), Run(WithClaims(50_001)));
        Assert.Equal("5-year loss ratio 72% > 60%", Engine.Evaluate(WithClaims(36_000)).Reasons.Single().Message);
    }

    [Fact]
    public void No_premium_means_no_loss_ratio_rule()
    {
        var rec = WithClaims(1_000_000);
        rec.LossYears.Clear();
        Assert.DoesNotContain(Engine.Evaluate(rec).Reasons, r => r.RuleId == "LOSS_RATIO");
    }

    [Fact]
    public void Frequency_and_large_loss()
    {
        Assert.Equal((DecisionOutcome.Refer, "LOSS_FREQUENCY"), Run(WithClaims(1_000, 1_000, 1_000, 1_000, 1_000)));
        Assert.Equal(DecisionOutcome.Accept, Run(WithClaims(1_000, 1_000, 1_000, 1_000)).Outcome);
        var rec = WithClaims(260_000);
        rec.LossYears.ForEach(y => y.EarnedPremium = 1_000_000);
        var hit = Engine.Evaluate(rec).Reasons.Single();
        Assert.Equal(("LARGE_LOSS", "claims[C0].incurred"), (hit.RuleId, hit.Fields.Single()));   // claim key: alphanumerics only
    }

    [Fact]
    public void Most_severe_outcome_wins_and_every_rule_is_listed()
    {
        var rec = Clean(l => { l.YearBuilt = 1940; l.Zip = "33101"; l.Construction = "frame"; });
        rec.Insured.NaicsCode = "721110";
        var (outcome, rules) = Run(rec);
        Assert.Equal(DecisionOutcome.Decline, outcome);
        Assert.Equal("BUILDING_AGE,CLASS_REFER,HURRICANE_ZONE", rules);
    }

    [Fact]
    public void Flagged_fields_add_a_caveat_to_the_rules_that_use_them()
    {
        var r = Engine.Evaluate(Clean(l => l.ProtectionClass = 10), new HashSet<string> { "locations[1].protection_class", "insured.dba" });
        Assert.Equal("location 1: protection class 10 (depends on fields under review: locations[1].protection_class)", r.Reasons.Single().Message);
    }

    [Fact]
    public void Rules_file_with_an_unknown_required_field_fails_at_startup()
    {
        Yaml.RequiredFields.Location.Add("basement_depth");
        try
        {
            Assert.Throws<InvalidOperationException>(() => new RulesEngine(Yaml));
        }
        finally
        {
            Yaml.RequiredFields.Location.Remove("basement_depth");
        }
    }

    [Fact]
    public void Rules_file_with_unknown_keys_is_rejected()
    {
        var path = Path.GetTempFileName();
        File.WriteAllText(path, File.ReadAllText(RepoPaths.AppetiteYaml) + "\nsurprise_rule: 1\n");
        try
        {
            Assert.ThrowsAny<Exception>(() => AppetiteRules.Load(path));
        }
        finally
        {
            File.Delete(path);
        }
    }
}
