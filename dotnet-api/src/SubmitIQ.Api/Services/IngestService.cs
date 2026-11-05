using System.Globalization;
using System.Text.Json.Nodes;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Contracts;
using SubmitIQ.Api.Data;
using SubmitIQ.Api.Domain;

namespace SubmitIQ.Api.Services;

public sealed class SubmissionExistsException(string id) : Exception($"submission {id} already exists");

/// <summary>Turns one Python PipelineResult into rows: submission, fields, review tasks, decision, audit event.</summary>
public sealed class IngestService(SubmitIqDbContext db, FieldRegistry registry, TimeProvider clock)
{
    /// <summary>Checks the payload beyond attribute validation. Returns field -> messages (empty when valid).</summary>
    public Dictionary<string, string[]> Validate(PipelineResultDto dto)
    {
        var errors = new Dictionary<string, string[]>();
        var recordId = dto.Record?["submission_id"]?.GetValue<string>();
        if (recordId is not null && recordId != dto.SubmissionId)
            errors["record.submission_id"] = [$"'{recordId}' does not match submission_id '{dto.SubmissionId}'"];
        foreach (var (key, prov) in dto.Provenance)
        {
            if (registry.Find(key) is null)
                errors[$"provenance.{key}"] = ["unknown field path (not in the field registry)"];
            else if (prov.Path != key)
                errors[$"provenance.{key}.path"] = [$"path '{prov.Path}' does not match its key"];
        }
        return errors;
    }

    public async Task<IngestResult> IngestAsync(PipelineResultDto dto, CancellationToken ct)
    {
        var id = dto.SubmissionId!;
        if (await db.Submissions.AnyAsync(s => s.Id == id, ct))
            throw new SubmissionExistsException(id);
        var now = clock.GetUtcNow();
        var record = dto.Record!;

        var submission = new Submission
        {
            Id = id, Pipeline = dto.Pipeline!, RecordJson = record.ToJsonString(), ReceivedAt = now, UpdatedAt = now,
            InsuredName = Truncate(RecordPaths.Get(record, "insured.named_insured")?.ToString(), 256),
            TotalTiv = ToDecimal(RecordPaths.Get(record, "totals.total_tiv")),
            EffectiveDate = DateOnly.TryParseExact(RecordPaths.Get(record, "policy.effective_date")?.ToString(), "yyyy-MM-dd",
                CultureInfo.InvariantCulture, DateTimeStyles.None, out var eff) ? eff : null,
        };

        foreach (var (path, prov) in dto.Provenance.OrderBy(p => p.Key, StringComparer.Ordinal))
        {
            var spec = registry.Find(path)!;
            var cite = prov.Citations.FirstOrDefault();
            submission.Fields.Add(new ExtractedField
            {
                Path = path, ValueJson = Truncate(RecordPaths.Get(record, path)?.ToJsonString(), 2000),
                Confidence = prov.Confidence, Status = prov.Status!.Value, IsCritical = spec.Critical,
                Extractor = prov.Extractor, CitationDocument = Truncate(cite?.Doc, 256), CitationPage = cite?.Page,
                CitationLocator = Truncate(cite?.Locator, 128), CitationSnippet = Truncate(cite?.Snippet, 500),
            });
            if (prov.Status != FieldStatus.Ok)
            {
                submission.ReviewTasks.Add(new ReviewTask
                {
                    FieldPath = path, FieldStatus = prov.Status!.Value, Priority = Priority(prov.Status.Value, spec.Critical),
                    Reason = Truncate(string.Join("; ", prov.Reasons.TakeLast(2)), 1000) ?? "", Status = ReviewTaskStatus.Open,
                    CreatedAt = now,
                });
            }
        }

        // The Python pipeline's own decision is kept as provenance; Step 3's C# engine adds its own.
        if (dto.Decision?.Outcome is { } outcome)
        {
            submission.Decisions.Add(new Decision
            {
                Outcome = outcome, Source = "python-pipeline", RulesVersion = "", DecidedAt = now,
                Reasons = dto.Decision.Reasons.Select(r => new DecisionReason
                    { RuleId = r.RuleId, Outcome = r.Outcome, Message = r.Message, Fields = r.Fields }).ToList(),
            });
        }

        submission.Status = submission.ReviewTasks.Count > 0 || dto.NeedsReview ? SubmissionStatus.NeedsReview : SubmissionStatus.AutoCleared;
        db.Submissions.Add(submission);
        db.AuditEvents.Add(new AuditEvent
        {
            SubmissionId = id, EventType = AuditEventType.SubmissionIngested, Actor = $"pipeline:{dto.Pipeline}",
            Comment = $"{submission.Fields.Count} fields, {submission.ReviewTasks.Count} flagged", OccurredAt = now,
        });
        try
        {
            await db.SaveChangesAsync(ct);
        }
        catch (DbUpdateException e) when (e.InnerException is SqlException { Number: 2627 or 2601 })
        {
            throw new SubmissionExistsException(id);   // primary-key violation: lost a race with a concurrent POST of the same id
        }
        return new IngestResult(id, submission.Status, submission.Fields.Count, submission.ReviewTasks.Count, dto.Decision?.Outcome);
    }

    /// <summary>Critical fields first, then conflicts/invalid values, then missing, then low confidence.</summary>
    public static int Priority(FieldStatus status, bool critical) =>
        (critical ? 100 : 0) + status switch
        {
            FieldStatus.Conflict or FieldStatus.Invalid => 50,
            FieldStatus.Missing => 40,
            FieldStatus.LowConfidence => 10,
            _ => 0,
        };

    private static string? Truncate(string? s, int max) => s is null || s.Length <= max ? s : s[..max];

    private static decimal? ToDecimal(JsonNode? n) =>
        n is JsonValue v && v.TryGetValue<double>(out var d) ? (decimal)d : null;
}
