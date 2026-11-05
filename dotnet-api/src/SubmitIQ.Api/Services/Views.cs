using System.Text.Json;
using SubmitIQ.Api.Contracts;
using SubmitIQ.Api.Domain;

namespace SubmitIQ.Api.Services;

/// <summary>Entity -> response model mapping.</summary>
public static class Views
{
    public static JsonElement? Value(string? json) => json is null ? null : JsonDocument.Parse(json).RootElement.Clone();

    public static CitationView Citation(ExtractedField f) =>
        new(f.CitationDocument, f.CitationPage, f.CitationLocator, f.CitationSnippet);

    public static FieldView Field(ExtractedField f) =>
        new(f.Path, Value(f.ValueJson), f.Confidence, f.Status, f.IsCritical, f.Extractor, Citation(f));

    public static DecisionView Decision(Decision d) =>
        new(d.Id, d.Outcome, d.Source, d.RulesVersion, d.DecidedAt, d.Reasons);

    public static ReviewTaskView Task(ReviewTask t, string? insuredName, ExtractedField? field) =>
        new(t.Id, t.SubmissionId, insuredName, t.FieldPath, t.FieldStatus, field?.IsCritical ?? false, t.Reason, t.Priority,
            t.Status, Value(field?.ValueJson), field is null ? null : Citation(field), t.CreatedAt, t.ResolvedAt, t.ResolvedBy,
            t.Resolution);
}
