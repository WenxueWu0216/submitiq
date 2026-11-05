namespace SubmitIQ.Api.Domain;

/// <summary>An appetite decision. A submission keeps every decision made (after ingest, after each review).</summary>
public class Decision
{
    public long Id { get; set; }
    public string SubmissionId { get; set; } = "";
    public DecisionOutcome Outcome { get; set; }
    public string Source { get; set; } = "";              // "rules-dotnet" or "python-pipeline"
    public string RulesVersion { get; set; } = "";
    public DateTimeOffset DecidedAt { get; set; }
    public List<DecisionReason> Reasons { get; set; } = [];

    public Submission? Submission { get; set; }
}

/// <summary>One triggered rule. Stored as a JSON column on the Decision row.</summary>
public class DecisionReason
{
    public string RuleId { get; set; } = "";
    public DecisionOutcome Outcome { get; set; }
    public string Message { get; set; } = "";
    public List<string> Fields { get; set; } = [];
}
