namespace SubmitIQ.Api.Domain;

/// <summary>
/// One broker submission as produced by the Python extraction pipeline.
/// RecordJson keeps the full canonical record (the rules engine reads it). The
/// columns next to it are the values the review queue lists and filters on.
/// </summary>
public class Submission
{
    public string Id { get; set; } = "";                 // e.g. "SUB-0003", from the pipeline
    public string Pipeline { get; set; } = "";           // pipeline variant that produced it
    public SubmissionStatus Status { get; set; }
    public string? InsuredName { get; set; }
    public decimal? TotalTiv { get; set; }
    public DateOnly? EffectiveDate { get; set; }
    public string RecordJson { get; set; } = "{}";
    public DateTimeOffset ReceivedAt { get; set; }
    public DateTimeOffset UpdatedAt { get; set; }
    public byte[] RowVersion { get; set; } = [];          // optimistic concurrency for reviewer edits

    public List<ExtractedField> Fields { get; set; } = [];
    public List<Decision> Decisions { get; set; } = [];
    public List<ReviewTask> ReviewTasks { get; set; } = [];
}
