using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Contracts;
using SubmitIQ.Api.Data;
using SubmitIQ.Api.Domain;

namespace SubmitIQ.Api.Services;

public sealed class NotFoundException(string message) : Exception(message);

public sealed class ConflictException(string message) : Exception(message);

public sealed class InvalidValueException(string message) : Exception(message);

public sealed class ReviewService(SubmitIqDbContext db, FieldRegistry registry, DecisionService decider, TimeProvider clock)
{
    public async Task<PagedResult<ReviewTaskView>> QueueAsync(ReviewTaskStatus status, int page, int pageSize, CancellationToken ct)
    {
        var query = db.ReviewTasks.AsNoTracking().Where(t => t.Status == status);
        var total = await query.CountAsync(ct);
        var rows = await query
            .OrderByDescending(t => t.Priority).ThenBy(t => t.CreatedAt).ThenBy(t => t.Id)
            .Skip((page - 1) * pageSize).Take(pageSize)
            .Select(t => new
            {
                Task = t,
                t.Submission!.InsuredName,
                Field = db.ExtractedFields.FirstOrDefault(f => f.SubmissionId == t.SubmissionId && f.Path == t.FieldPath),
            })
            .ToListAsync(ct);
        return new PagedResult<ReviewTaskView>(rows.Select(r => Views.Task(r.Task, r.InsuredName, r.Field)).ToList(),
                                               page, pageSize, total);
    }

    public async Task<ResolveResult> ResolveAsync(long taskId, ResolveRequest req, CancellationToken ct)
    {
        var task = await db.ReviewTasks.Include(t => t.Submission).SingleOrDefaultAsync(t => t.Id == taskId, ct)
                   ?? throw new NotFoundException($"review task {taskId} does not exist");
        if (task.Status == ReviewTaskStatus.Resolved)
            throw new ConflictException($"review task {taskId} was already resolved by {task.ResolvedBy} at {task.ResolvedAt:O}");
        var submission = task.Submission!;
        var field = await db.ExtractedFields.SingleOrDefaultAsync(f => f.SubmissionId == task.SubmissionId && f.Path == task.FieldPath, ct);
        var now = clock.GetUtcNow();
        var reviewer = req.Reviewer!.Trim();
        var oldValue = field?.ValueJson;
        string? newValue = oldValue;

        if (req.Action == ResolveAction.Correct)
        {
            newValue = NormalizeValue(task.FieldPath, req.Value);
            var record = JsonNode.Parse(submission.RecordJson)!.AsObject();
            if (!RecordPaths.Set(record, task.FieldPath, newValue is null ? null : JsonNode.Parse(newValue)))
                throw new InvalidValueException($"field {task.FieldPath} cannot be set on this record (no such location/claim/year)");
            submission.RecordJson = record.ToJsonString();
            if (field is null)
            {
                field = new ExtractedField { SubmissionId = submission.Id, Path = task.FieldPath,
                                             IsCritical = registry.Find(task.FieldPath)?.Critical ?? false };
                db.ExtractedFields.Add(field);
            }
            field.ValueJson = newValue;
            field.Confidence = 1.0;
            field.Extractor = $"human:{reviewer}";
        }
        if (field is not null)
            field.Status = FieldStatus.Ok;

        task.Status = ReviewTaskStatus.Resolved;
        task.ResolvedAt = now;
        task.ResolvedBy = reviewer;
        task.Resolution = req.Action == ResolveAction.Correct ? ReviewResolution.Corrected : ReviewResolution.Confirmed;

        var stillOpen = await db.ReviewTasks
            .Where(t => t.SubmissionId == submission.Id && t.Status == ReviewTaskStatus.Open && t.Id != taskId)
            .Select(t => t.FieldPath).ToListAsync(ct);
        var open = stillOpen.Count;
        submission.Status = open == 0 ? SubmissionStatus.Approved : SubmissionStatus.NeedsReview;
        submission.UpdatedAt = now;   // bumps the rowversion: two reviewers editing the same submission -> 409

        db.AuditEvents.Add(new AuditEvent
        {
            SubmissionId = submission.Id, ReviewTaskId = task.Id, Actor = reviewer, FieldPath = task.FieldPath,
            EventType = req.Action == ResolveAction.Correct ? AuditEventType.FieldCorrected : AuditEventType.FieldConfirmed,
            OldValueJson = oldValue, NewValueJson = newValue, Comment = req.Comment, OccurredAt = now,
        });

        // Re-run the rules (after the field event, so the audit trail reads cause -> effect) on the reviewed record: a corrected TIV or year built can change the outcome.
        var previous = await db.Decisions.AsNoTracking()
            .Where(d => d.SubmissionId == submission.Id && d.Source == DecisionService.Source)
            .OrderByDescending(d => d.DecidedAt).ThenByDescending(d => d.Id).FirstOrDefaultAsync(ct);
        var decision = decider.Decide(submission.Id, JsonNode.Parse(submission.RecordJson)!.AsObject(),
                                      stillOpen.ToHashSet(), now);
        db.Decisions.Add(decision);
        if (previous is null || previous.Outcome != decision.Outcome)
        {
            db.AuditEvents.Add(new AuditEvent
            {
                SubmissionId = submission.Id, ReviewTaskId = task.Id, Actor = DecisionService.Source,
                EventType = AuditEventType.DecisionMade, OldValueJson = previous is null ? null : $"\"{Wire(previous.Outcome)}\"",
                NewValueJson = $"\"{Wire(decision.Outcome)}\"", Comment = $"after review of {task.FieldPath}", OccurredAt = now,
            });
        }
        try
        {
            await db.SaveChangesAsync(ct);
        }
        catch (DbUpdateConcurrencyException)
        {
            throw new ConflictException($"submission {submission.Id} was changed by someone else; reload and try again");
        }
        return new ResolveResult(Views.Task(task, submission.InsuredName, field), submission.Status, open, decision.Outcome);
    }

    private static string Wire(DecisionOutcome o) => o.ToString().ToLowerInvariant();

    /// <summary>Checks a corrected value against the field's kind and returns it as compact JSON (null clears).</summary>
    public string? NormalizeValue(string path, JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Undefined)
            throw new InvalidValueException("'value' is required when action is 'correct' (send null to clear the field)");
        if (value.ValueKind == JsonValueKind.Null)
            return null;
        var kind = registry.Find(path)?.Kind ?? throw new InvalidValueException($"unknown field {path}");
        var ok = kind switch
        {
            "money" => value.ValueKind == JsonValueKind.Number && value.GetDouble() >= 0,
            "int" or "approx_int" => value.ValueKind == JsonValueKind.Number && value.TryGetInt64(out _),
            "bool" => value.ValueKind is JsonValueKind.True or JsonValueKind.False,
            "date" => value.ValueKind == JsonValueKind.String &&
                      DateOnly.TryParseExact(value.GetString(), "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out _),
            _ => value.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(value.GetString()),
        };
        if (!ok)
            throw new InvalidValueException(kind switch
            {
                "money" => $"{path} expects a non-negative number",
                "int" or "approx_int" => $"{path} expects an integer",
                "bool" => $"{path} expects true or false",
                "date" => $"{path} expects a date as \"YYYY-MM-DD\"",
                _ => $"{path} expects a non-empty string",
            });
        return value.GetRawText();
    }
}
