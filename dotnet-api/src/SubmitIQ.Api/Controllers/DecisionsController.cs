using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Contracts;
using SubmitIQ.Api.Data;
using SubmitIQ.Api.Services;

namespace SubmitIQ.Api.Controllers;

[ApiController]
[Route("decisions")]
[Produces("application/json")]
public sealed class DecisionsController(SubmitIqDbContext db) : ControllerBase
{
    /// <summary>The latest appetite decision for a submission, plus every earlier one.</summary>
    [HttpGet("{submissionId}")]
    [ProducesResponseType<DecisionHistory>(StatusCodes.Status200OK)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status404NotFound)]
    public async Task<IActionResult> Get(string submissionId, CancellationToken ct)
    {
        if (!await db.Submissions.AnyAsync(s => s.Id == submissionId, ct))
            return Problem(statusCode: StatusCodes.Status404NotFound, title: "Submission not found",
                           detail: $"no submission with id '{submissionId}'");
        var history = await db.Decisions.AsNoTracking().Where(d => d.SubmissionId == submissionId)
            .OrderByDescending(d => d.DecidedAt).ThenByDescending(d => d.Id).ToListAsync(ct);
        var views = history.Select(Views.Decision).ToList();
        return Ok(new DecisionHistory(submissionId, views.FirstOrDefault(), views));
    }
}
