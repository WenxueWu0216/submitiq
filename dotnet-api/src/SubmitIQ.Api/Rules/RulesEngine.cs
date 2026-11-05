using System.Globalization;
using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Services;

namespace SubmitIQ.Api.Rules;

public sealed record RulesResult(DecisionOutcome Outcome, string RulesVersion, IReadOnlyList<DecisionReason> Reasons);

/// <summary>
/// Deterministic appetite rules: a rule-for-rule port of submitiq/rules_engine.py, driven by the
/// same rules/appetite.yaml. Rule order, comparison operators (strict ">" vs ">="), rule IDs, the
/// fields each rule cites and the message text all match the Python engine, so the two can be
/// compared hit for hit (tests/.../RulesParityTests.cs).
/// </summary>
public sealed class RulesEngine
{
    private readonly AppetiteRules _r;
    private readonly List<DecisionOutcome> _order;

    public RulesEngine(AppetiteRules rules)
    {
        _r = rules;
        _order = rules.OutcomeOrder.Select(Parse).ToList();
        if (_order.Count != 3)
            throw new InvalidOperationException("appetite.yaml outcome_order must list accept, refer and decline");
        // Fail at startup, not on the first submission, if the YAML names a location field we cannot read.
        foreach (var f in rules.RequiredFields.Location)
            new LocationPart().Required(f);
    }

    public string Version => _r.Version;

    public RulesResult Evaluate(RuleInput rec, IReadOnlySet<string>? flaggedPaths = null)
    {
        var hits = new List<DecisionReason>();
        hits.AddRange(Class(rec));
        hits.AddRange(AccountTiv(rec));
        hits.AddRange(Losses(rec));
        foreach (var loc in rec.Locations)
        {
            hits.AddRange(MissingLocation(loc));
            hits.AddRange(LocationTiv(loc));
            hits.AddRange(ConstructionProtection(loc));
            hits.AddRange(Hurricane(loc));
            hits.AddRange(Earthquake(loc));
            hits.AddRange(Sprinklers(loc));
            hits.AddRange(Age(rec, loc));
        }
        var outcome = hits.Count == 0 ? DecisionOutcome.Accept : hits.Select(h => h.Outcome).MaxBy(o => _order.IndexOf(o));
        if (flaggedPaths is { Count: > 0 })
        {
            foreach (var h in hits)
            {
                var dep = h.Fields.Where(flaggedPaths.Contains).Order(StringComparer.Ordinal).ToList();
                if (dep.Count > 0)
                    h.Message += $" (depends on fields under review: {string.Join(", ", dep)})";
            }
        }
        return new RulesResult(outcome, _r.Version, hits);
    }

    // ---------------------------------------------------------------- account level

    private IEnumerable<DecisionReason> Class(RuleInput rec)
    {
        var naics = rec.Insured.NaicsCode;
        string[] f = ["insured.naics_code"];
        if (naics is null)
            yield return Hit("MISSING_INFO", DecisionOutcome.Refer, "NAICS code missing", f);
        else if (_r.Classes.Decline.TryGetValue(naics, out var d))
            yield return Hit("CLASS_PROHIBITED", DecisionOutcome.Decline, $"NAICS {naics} ({d}) is prohibited", f);
        else if (_r.Classes.Refer.TryGetValue(naics, out var r))
            yield return Hit("CLASS_REFER", DecisionOutcome.Refer, $"NAICS {naics} ({r}) requires referral", f);
        else if (!_r.Classes.Accept.ContainsKey(naics))
            yield return Hit("CLASS_UNKNOWN", DecisionOutcome.Refer, $"NAICS {naics} not in appetite guide", f);
    }

    private IEnumerable<DecisionReason> AccountTiv(RuleInput rec)
    {
        var tiv = rec.Totals.TotalTiv;
        var lim = _r.Tiv.AccountReferAbove;
        if (tiv is not null && tiv > lim)
            yield return Hit("ACCOUNT_TIV", DecisionOutcome.Refer, $"account TIV ${Money(tiv.Value)} > ${Money(lim)}", ["totals.total_tiv"]);
    }

    private IEnumerable<DecisionReason> Losses(RuleInput rec)
    {
        var l = _r.Losses;
        // Same summation order as Python's sum(), so the double result is bit-identical.
        var incurred = 0.0;
        foreach (var c in rec.Claims)
            incurred += c.Incurred ?? 0;
        var premium = 0.0;
        foreach (var y in rec.LossYears)
            premium += y.EarnedPremium ?? 0;
        string[] lrFields = ["totals.five_year_incurred", "totals.five_year_premium"];
        if (premium > 0)
        {
            var lr = incurred / premium;
            if (lr > l.LossRatioDeclineAbove)
                yield return Hit("LOSS_RATIO", DecisionOutcome.Decline, $"5-year loss ratio {Pct(lr)} > {Pct(l.LossRatioDeclineAbove)}", lrFields);
            else if (lr > l.LossRatioReferAbove)
                yield return Hit("LOSS_RATIO", DecisionOutcome.Refer, $"5-year loss ratio {Pct(lr)} > {Pct(l.LossRatioReferAbove)}", lrFields);
        }
        var n = rec.Claims.Count;
        if (n >= l.ClaimCountReferAtOrAbove)
            yield return Hit("LOSS_FREQUENCY", DecisionOutcome.Refer, $"{n} claims in 5 years",
                             rec.LossYears.Select(y => $"loss_years[{y.PolicyYear}].claim_count"));
        foreach (var c in rec.Claims)
        {
            if ((c.Incurred ?? 0) > l.LargeLossReferAbove)
                yield return Hit("LARGE_LOSS", DecisionOutcome.Refer,
                                 $"claim {c.ClaimNumber} incurred ${Money(c.Incurred!.Value)} ({c.Cause ?? "cause n/a"})",
                                 [$"claims[{RecordPaths.ClaimKey(c.ClaimNumber)}].incurred"]);
        }
    }

    // ---------------------------------------------------------------- location level

    private IEnumerable<DecisionReason> MissingLocation(LocationPart loc)
    {
        var miss = _r.RequiredFields.Location.Where(f => loc.Required(f) is null).ToList();
        if (miss.Count > 0)
            yield return Hit("MISSING_INFO", DecisionOutcome.Refer, $"location {loc.LocNumber}: missing {string.Join(", ", miss)}",
                             miss.Select(f => $"locations[{loc.LocNumber}].{f}"));
    }

    private IEnumerable<DecisionReason> LocationTiv(LocationPart loc)
    {
        var t = loc.Tiv ?? 0;
        string[] f = [$"locations[{loc.LocNumber}].tiv"];
        if (t > _r.Tiv.LocationDeclineAbove)
            yield return Hit("LOCATION_TIV", DecisionOutcome.Decline,
                             $"location {loc.LocNumber} TIV ${Money(t)} > ${Money(_r.Tiv.LocationDeclineAbove)}", f);
        else if (t > _r.Tiv.LocationReferAbove)
            yield return Hit("LOCATION_TIV", DecisionOutcome.Refer,
                             $"location {loc.LocNumber} TIV ${Money(t)} > ${Money(_r.Tiv.LocationReferAbove)}", f);
    }

    private IEnumerable<DecisionReason> ConstructionProtection(LocationPart loc)
    {
        var cp = _r.ConstructionProtection;
        var k = loc.LocNumber;
        if (loc.ProtectionClass is not { } pc)
            yield break;
        if (loc.Construction == "frame" && pc >= cp.DeclineFrameWithPcAtOrAbove)
            yield return Hit("FRAME_POOR_PROTECTION", DecisionOutcome.Decline, $"location {k}: frame construction with protection class {pc}",
                             [$"locations[{k}].construction", $"locations[{k}].protection_class"]);
        if (pc >= cp.ReferPcAtOrAbove)
            yield return Hit("POOR_PROTECTION", DecisionOutcome.Refer, $"location {k}: protection class {pc}", [$"locations[{k}].protection_class"]);
    }

    private IEnumerable<DecisionReason> Hurricane(LocationPart loc)
    {
        var z = _r.CatZones;
        var k = loc.LocNumber;
        if (!z.HurricaneTier1Zip3.Contains(Zip3(loc.Zip)))
            yield break;
        if (loc.Construction == "frame")
            yield return Hit("HURRICANE_ZONE", DecisionOutcome.Decline, $"location {k}: frame building in tier-1 hurricane zone (ZIP {loc.Zip})",
                             [$"locations[{k}].zip", $"locations[{k}].construction"]);
        else if ((loc.Tiv ?? 0) > z.HurricaneReferLocationTivAbove)
            yield return Hit("HURRICANE_ZONE", DecisionOutcome.Refer, $"location {k}: TIV ${Money(loc.Tiv!.Value)} in tier-1 hurricane zone (ZIP {loc.Zip})",
                             [$"locations[{k}].zip", $"locations[{k}].tiv"]);
    }

    private IEnumerable<DecisionReason> Earthquake(LocationPart loc)
    {
        var z = _r.CatZones;
        var k = loc.LocNumber;
        if (z.EarthquakeZip3.Contains(Zip3(loc.Zip)) && loc.Construction == "joisted_masonry"
            && loc.YearBuilt is { } yb && yb < z.EarthquakeReferJmBuiltBefore)
            yield return Hit("EARTHQUAKE_ZONE", DecisionOutcome.Refer, $"location {k}: joisted masonry built {yb} in earthquake zone",
                             [$"locations[{k}].zip", $"locations[{k}].construction", $"locations[{k}].year_built"]);
    }

    private IEnumerable<DecisionReason> Sprinklers(LocationPart loc)
    {
        var k = loc.LocNumber;
        if (loc.Sprinklered == false && (loc.Tiv ?? 0) > _r.Sprinklers.ReferUnsprinkleredLocationTivAbove)
            yield return Hit("UNSPRINKLERED", DecisionOutcome.Refer, $"location {k}: unsprinklered with TIV ${Money(loc.Tiv!.Value)}",
                             [$"locations[{k}].sprinklered", $"locations[{k}].tiv"]);
    }

    private IEnumerable<DecisionReason> Age(RuleInput rec, LocationPart loc)
    {
        var a = _r.Age;
        var k = loc.LocNumber;
        if (loc.YearBuilt is { } yb && yb < a.ReferYearBuiltBefore)
            yield return Hit("BUILDING_AGE", DecisionOutcome.Refer, $"location {k}: built {yb}", [$"locations[{k}].year_built"]);
        if (loc.RoofYear is { } ry && rec.Policy.EffectiveDate is { } eff && eff.Year - ry > a.ReferRoofAgeOverYears)
            yield return Hit("ROOF_AGE", DecisionOutcome.Refer, $"location {k}: roof {eff.Year - ry} years old at inception",
                             [$"locations[{k}].roof_year", "policy.effective_date"]);
    }

    // ---------------------------------------------------------------- helpers

    private static DecisionReason Hit(string id, DecisionOutcome outcome, string message, IEnumerable<string> fields) =>
        new() { RuleId = id, Outcome = outcome, Message = message, Fields = fields.ToList() };

    /// <summary>Python's (zip or "")[:3].</summary>
    private static string Zip3(string? zip) => (zip ?? "").Length > 3 ? zip![..3] : zip ?? "";

    /// <summary>Python f"{x:,.0f}": round half to even, thousands separators.</summary>
    private static string Money(double x) => Math.Round(x, MidpointRounding.ToEven).ToString("#,##0", CultureInfo.InvariantCulture);

    /// <summary>Python f"{x:.0%}": x * 100, round half to even, then "%".</summary>
    private static string Pct(double x) => Math.Round(x * 100, MidpointRounding.ToEven).ToString("0", CultureInfo.InvariantCulture) + "%";

    private static DecisionOutcome Parse(string s) => s switch
    {
        "accept" => DecisionOutcome.Accept,
        "refer" => DecisionOutcome.Refer,
        "decline" => DecisionOutcome.Decline,
        _ => throw new InvalidOperationException($"unknown outcome '{s}' in appetite.yaml outcome_order"),
    };
}
