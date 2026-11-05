using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Contracts;
using SubmitIQ.Api.Data;
using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Services;

namespace SubmitIQ.Api.Controllers;

[ApiController]
[Route("submissions")]
[Produces("application/json")]
public sealed class SubmissionsController(SubmitIqDbContext db, IngestService ingest) : ControllerBase
{
    /// <summary>Ingest one PipelineResult produced by the Python extraction pipeline.</summary>
    [HttpPost]
    [ProducesResponseType<IngestResult>(StatusCodes.Status201Created)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> Create(PipelineResultDto dto, CancellationToken ct)
    {
        var errors = ingest.Validate(dto);
        if (errors.Count > 0)
            return ValidationProblem(new ValidationProblemDetails(errors));
        try
        {
            var result = await ingest.IngestAsync(dto, ct);
            return CreatedAtAction(nameof(Get), new { id = result.Id }, result);
        }
        catch (SubmissionExistsException e)
        {
            return Problem(statusCode: StatusCodes.Status409Conflict, title: "Submission already exists", detail: e.Message);
        }
    }

    [HttpGet("{id}")]
    [ProducesResponseType<SubmissionView>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Get(string id, CancellationToken ct)
    {
        var s = await db.Submissions.AsNoTracking().AsSplitQuery()
            .Include(x => x.Fields.OrderBy(f => f.Path))
            .Include(x => x.Decisions)
            .SingleOrDefaultAsync(x => x.Id == id, ct);
        if (s is null)
            return Problem(statusCode: StatusCodes.Status404NotFound, title: "Submission not found", detail: $"no submission with id '{id}'");
        var open = await db.ReviewTasks.CountAsync(t => t.SubmissionId == id && t.Status == ReviewTaskStatus.Open, ct);
        var latest = s.Decisions.OrderByDescending(d => d.DecidedAt).ThenByDescending(d => d.Id).FirstOrDefault();
        return Ok(new SubmissionView(s.Id, s.Pipeline, s.Status, s.InsuredName, s.TotalTiv, s.EffectiveDate, s.ReceivedAt,
                                     s.UpdatedAt, open, latest is null ? null : Views.Decision(latest),
                                     s.Fields.Select(Views.Field).ToList()));
    }
}
