using System.Text.Json;
using System.Text.Json.Nodes;
using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Rules;
using SubmitIQ.Api.Tests.Infrastructure;
using Xunit.Abstractions;

namespace SubmitIQ.Api.Tests.Rules;

/// <summary>
/// Runs all 120 labeled submissions through the C# engine and compares with the decisions the Python
/// engine recorded for the same records (contracts/python_decisions.json, exported by
/// scripts/export_contracts.py). Both engines read the same rules/appetite.yaml.
/// </summary>
public class RulesParityTests(ITestOutputHelper output)
{
    private static readonly RulesEngine Engine = new(AppetiteRules.Load(RepoPaths.AppetiteYaml));

    public sealed record Case(string Id, JsonObject Record, string ExpectedDecision, List<string> ExpectedReasons);

    public static IReadOnlyList<Case> LoadCases() =>
        Directory.GetFiles(RepoPaths.Submissions, "ground_truth.json", SearchOption.AllDirectories)
            .Order(StringComparer.Ordinal)
            .Select(path =>
            {
                var gt = JsonNode.Parse(File.ReadAllText(path))!.AsObject();
                var record = gt["record"]!.AsObject();
                var meta = gt["meta"]!.AsObject();
                return new Case(record["submission_id"]!.GetValue<string>(), record,
                                meta["expected_decision"]!.GetValue<string>(),
                                meta["expected_reasons"]!.AsArray().Select(n => n!.GetValue<string>()).ToList());
            })
            .ToList();

    private static Dictionary<string, JsonObject> PythonDecisions() =>
        JsonNode.Parse(File.ReadAllText(Path.Combine(RepoPaths.Contracts, "python_decisions.json")))!.AsObject()
            .ToDictionary(kv => kv.Key, kv => kv.Value!.AsObject());

    private static string Wire(DecisionOutcome o) => o.ToString().ToLowerInvariant();

    private static string Hit(string id, string outcome, IEnumerable<string> fields) => $"{id}/{outcome}[{string.Join(",", fields)}]";

    [Fact]
    public void Csharp_engine_matches_recorded_python_decisions_on_all_120_submissions()
    {
        var cases = LoadCases();
        var python = PythonDecisions();
        Assert.Equal(120, cases.Count);
        Assert.Equal(cases.Select(c => c.Id).Order(), python.Keys.Order());

        int outcomeMatch = 0, hitsMatch = 0, messagesMatch = 0;
        var mismatches = new List<string>();
        foreach (var c in cases)
        {
            var cs = Engine.Evaluate(RuleInput.From(c.Record));
            var py = python[c.Id];
            var pyReasons = py["reasons"]!.AsArray().Select(n => n!.AsObject()).ToList();

            var csHits = cs.Reasons.Select(r => Hit(r.RuleId, Wire(r.Outcome), r.Fields)).ToList();
            var pyHits = pyReasons.Select(r => Hit(r["rule_id"]!.GetValue<string>(), r["outcome"]!.GetValue<string>(),
                                                   r["fields"]!.AsArray().Select(f => f!.GetValue<string>()))).ToList();
            var csMessages = cs.Reasons.Select(r => r.Message).ToList();
            var pyMessages = pyReasons.Select(r => r["message"]!.GetValue<string>()).ToList();

            var o = Wire(cs.Outcome) == py["outcome"]!.GetValue<string>();
            var h = csHits.SequenceEqual(pyHits);
            var m = csMessages.SequenceEqual(pyMessages);
            outcomeMatch += o ? 1 : 0;
            hitsMatch += h ? 1 : 0;
            messagesMatch += m ? 1 : 0;
            if (!(o && h && m))
                mismatches.Add($"{c.Id}: C# {Wire(cs.Outcome)} {string.Join(" ", csHits)} | Python {py["outcome"]} {string.Join(" ", pyHits)}"
                               + (m ? "" : $"\n    C# messages: {JsonSerializer.Serialize(csMessages)}\n    Py messages: {JsonSerializer.Serialize(pyMessages)}"));
        }

        output.WriteLine($"outcome match:            {outcomeMatch}/{cases.Count}");
        output.WriteLine($"rule hits match (ordered): {hitsMatch}/{cases.Count}");
        output.WriteLine($"messages match:           {messagesMatch}/{cases.Count}");
        output.WriteLine($"rule hits compared:       {python.Values.Sum(p => p["reasons"]!.AsArray().Count)}");
        foreach (var line in mismatches)
            output.WriteLine("MISMATCH " + line);
        Assert.Empty(mismatches);
    }

    /// <summary>
    /// None of the 120 records lands on a .5 rounding boundary, so the parity test alone cannot tell
    /// half-even from half-away-from-zero. Expected strings were produced by Python itself:
    ///   f"{1.125:.0%}" == "112%", f"{0.625:.0%}" == "62%", f"{250000.5:,.0f}" == "250,000", f"{250001.5:,.0f}" == "250,002"
    /// </summary>
    [Theory]
    [InlineData(112_500.0, "5-year loss ratio 112% > 100%")]   // loss ratio exactly 1.125
    [InlineData(62_500.0, "5-year loss ratio 62% > 60%")]      // loss ratio exactly 0.625
    public void Loss_ratio_rounds_half_to_even_like_python(double incurred, string expected)
    {
        var rec = new RuleInput
        {
            Insured = new InsuredPart { NaicsCode = "493110" },
            Claims = [new ClaimPart { ClaimNumber = "C1", Incurred = incurred }],
            LossYears = [new LossYearPart { PolicyYear = 2025, EarnedPremium = 100_000.0 }],
        };
        Assert.Equal(expected, Assert.Single(Engine.Evaluate(rec).Reasons, r => r.RuleId == "LOSS_RATIO").Message);
    }

    [Theory]
    [InlineData(250_000.5, "claim C1 incurred $250,000 (Fire)")]
    [InlineData(250_001.5, "claim C1 incurred $250,002 (Fire)")]
    public void Money_rounds_half_to_even_like_python(double incurred, string expected)
    {
        var rec = new RuleInput
        {
            Insured = new InsuredPart { NaicsCode = "493110" },
            Claims = [new ClaimPart { ClaimNumber = "C1", Incurred = incurred, Cause = "Fire" }],
            LossYears = [new LossYearPart { PolicyYear = 2025, EarnedPremium = 100_000_000.0 }],
        };
        Assert.Equal(expected, Assert.Single(Engine.Evaluate(rec).Reasons, r => r.RuleId == "LARGE_LOSS").Message);
    }

    [Fact]
    public void Csharp_engine_agrees_with_the_independent_dataset_labels()
    {
        // The generator labels each record with a separately written implementation (data/synth/labels.py).
        var cases = LoadCases();
        var agree = 0;
        var bad = new List<string>();
        foreach (var c in cases)
        {
            var cs = Engine.Evaluate(RuleInput.From(c.Record));
            var ids = cs.Reasons.Select(r => r.RuleId).Distinct().Order(StringComparer.Ordinal).ToList();
            if (Wire(cs.Outcome) == c.ExpectedDecision && ids.SequenceEqual(c.ExpectedReasons))
                agree++;
            else
                bad.Add($"{c.Id}: C# {Wire(cs.Outcome)} [{string.Join(",", ids)}] vs label {c.ExpectedDecision} [{string.Join(",", c.ExpectedReasons)}]");
        }
        output.WriteLine($"agreement with dataset labels: {agree}/{cases.Count}");
        bad.ForEach(output.WriteLine);
        Assert.Empty(bad);
    }
}
