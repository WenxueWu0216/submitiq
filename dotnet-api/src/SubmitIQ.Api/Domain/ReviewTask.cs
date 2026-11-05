namespace SubmitIQ.Api.Domain;

/// <summary>One flagged field waiting for a human. The review queue is the open tasks.</summary>
public class ReviewTask
{
    public long Id { get; set; }
    public string SubmissionId { get; set; } = "";
    public string FieldPath { get; set; } = "";
    public FieldStatus FieldStatus { get; set; }
    public string Reason { get; set; } = "";
    public int Priority { get; set; }                     // higher first: critical fields, conflicts
    public ReviewTaskStatus Status { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset? ResolvedAt { get; set; }
    public string? ResolvedBy { get; set; }
    public ReviewResolution? Resolution { get; set; }

    public Submission? Submission { get; set; }
}
