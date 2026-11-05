using System.Text.Json.Nodes;
using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Rules;

namespace SubmitIQ.Api.Services;

/// <summary>Runs the C# rules engine over a record and turns the result into a Decision row.</summary>
public sealed class DecisionService(RulesEngine engine)
{
    public const string Source = "rules-dotnet";

    public Decision Decide(string submissionId, JsonObject record, IReadOnlySet<string> flaggedPaths, DateTimeOffset at)
    {
        var result = engine.Evaluate(RuleInput.From(record), flaggedPaths);
        return new Decision
        {
            SubmissionId = submissionId, Outcome = result.Outcome, Source = Source, RulesVersion = result.RulesVersion,
            DecidedAt = at, Reasons = result.Reasons.ToList(),
        };
    }
}
