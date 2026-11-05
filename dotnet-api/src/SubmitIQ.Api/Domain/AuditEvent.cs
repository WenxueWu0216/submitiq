namespace SubmitIQ.Api.Domain;

/// <summary>Append-only audit trail: who changed what, when, and from which value.</summary>
public class AuditEvent
{
    public long Id { get; set; }
    public string SubmissionId { get; set; } = "";
    public long? ReviewTaskId { get; set; }
    public AuditEventType EventType { get; set; }
    public string Actor { get; set; } = "";
    public string? FieldPath { get; set; }
    public string? OldValueJson { get; set; }
    public string? NewValueJson { get; set; }
    public string? Comment { get; set; }
    public DateTimeOffset OccurredAt { get; set; }
}
