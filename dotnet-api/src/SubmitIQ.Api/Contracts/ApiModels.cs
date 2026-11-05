using System.ComponentModel.DataAnnotations;
using System.Text.Json;
using SubmitIQ.Api.Domain;

namespace SubmitIQ.Api.Contracts;

public sealed record CitationView(string? Document, int? Page, string? Locator, string? Snippet);

public sealed record FieldView(string Path, JsonElement? Value, double? Confidence, FieldStatus Status, bool IsCritical,
                               string? Extractor, CitationView Citation);

public sealed record DecisionView(long Id, DecisionOutcome Outcome, string Source, string RulesVersion,
                                  DateTimeOffset DecidedAt, IReadOnlyList<DecisionReason> Reasons);

public sealed record SubmissionView(string Id, string Pipeline, SubmissionStatus Status, string? InsuredName, decimal? TotalTiv,
                                    DateOnly? EffectiveDate, DateTimeOffset ReceivedAt, DateTimeOffset UpdatedAt,
                                    int OpenReviewTasks, DecisionView? LatestDecision, IReadOnlyList<FieldView> Fields);

public sealed record IngestResult(string Id, SubmissionStatus Status, int Fields, int ReviewTasksCreated, DecisionOutcome? Decision);

public sealed record ReviewTaskView(long Id, string SubmissionId, string? InsuredName, string FieldPath, FieldStatus FieldStatus,
                                    bool IsCritical, string Reason, int Priority, ReviewTaskStatus Status,
                                    JsonElement? CurrentValue, CitationView? Citation, DateTimeOffset CreatedAt,
                                    DateTimeOffset? ResolvedAt, string? ResolvedBy, ReviewResolution? Resolution);

public sealed record PagedResult<T>(IReadOnlyList<T> Items, int Page, int PageSize, int TotalCount)
{
    public int TotalPages => PageSize == 0 ? 0 : (TotalCount + PageSize - 1) / PageSize;
}

public sealed record DecisionHistory(string SubmissionId, DecisionView? Latest, IReadOnlyList<DecisionView> History);

public enum ResolveAction { Confirm, Correct }

public sealed class ResolveRequest
{
    [Required, StringLength(128, MinimumLength = 1)]
    public string? Reviewer { get; set; }

    [Required]
    public ResolveAction? Action { get; set; }

    /// <summary>
    /// The corrected value, required for 'correct'. Explicit JSON null clears the field;
    /// an omitted value (ValueKind Undefined) is rejected so a missing key never wipes data.
    /// </summary>
    public JsonElement Value { get; set; }

    [StringLength(1000)]
    public string? Comment { get; set; }
}

public sealed record ResolveResult(ReviewTaskView Task, SubmissionStatus SubmissionStatus, int OpenReviewTasks);
