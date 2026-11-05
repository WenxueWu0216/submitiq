using System.ComponentModel.DataAnnotations;
using System.Text.Json.Nodes;
using SubmitIQ.Api.Domain;

namespace SubmitIQ.Api.Contracts;

// The JSON the Python pipeline writes (PipelineResult.model_dump_json()). Property names map
// to snake_case through the API-wide naming policy; fields the service does not use
// (alternatives, llm_calls, timings_ms, ...) are ignored.

public sealed class PipelineResultDto
{
    [Required, RegularExpression(@"^[A-Za-z0-9_-]{1,64}$", ErrorMessage = "letters, digits, '-' or '_', at most 64 characters")]
    public string? SubmissionId { get; set; }

    [Required, StringLength(64, MinimumLength = 1)]
    public string? Pipeline { get; set; }

    [Required]
    public JsonObject? Record { get; set; }

    public Dictionary<string, FieldProvenanceDto> Provenance { get; set; } = [];

    public PipelineDecisionDto? Decision { get; set; }

    public bool NeedsReview { get; set; }

    public List<string> ReviewReasons { get; set; } = [];
}

public sealed class FieldProvenanceDto
{
    [Required, StringLength(256)]
    public string? Path { get; set; }

    [Range(0.0, 1.0)]
    public double? Confidence { get; set; }

    [Required]
    public FieldStatus? Status { get; set; }

    [StringLength(64)]
    public string? Extractor { get; set; }

    public List<CitationDto> Citations { get; set; } = [];

    public List<string> Reasons { get; set; } = [];
}

public sealed class CitationDto
{
    public string? Doc { get; set; }
    public string? DocType { get; set; }
    public int? Page { get; set; }
    public string? Locator { get; set; }
    public string? Snippet { get; set; }
}

public sealed class PipelineDecisionDto
{
    public DecisionOutcome? Outcome { get; set; }
    public string? Source { get; set; }
    public List<RuleHitDto> Reasons { get; set; } = [];
}

public sealed class RuleHitDto
{
    public string RuleId { get; set; } = "";
    public DecisionOutcome Outcome { get; set; }
    public string Message { get; set; } = "";
    public List<string> Fields { get; set; } = [];
}
