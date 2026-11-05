namespace SubmitIQ.Api.Domain;

/// <summary>
/// One extracted value with its provenance. Path is the pipeline's flattened field
/// path, e.g. "locations[2].year_built" or "totals.total_tiv".
/// </summary>
public class ExtractedField
{
    public long Id { get; set; }
    public string SubmissionId { get; set; } = "";
    public string Path { get; set; } = "";
    public string? ValueJson { get; set; }                // JSON-encoded scalar; null = no value
    public double? Confidence { get; set; }
    public FieldStatus Status { get; set; }
    public bool IsCritical { get; set; }
    public string? Extractor { get; set; }                // form_parser, table_parser:local, llm:application, human:<name>
    public string? CitationDocument { get; set; }
    public int? CitationPage { get; set; }
    public string? CitationLocator { get; set; }
    public string? CitationSnippet { get; set; }

    public Submission? Submission { get; set; }
}
