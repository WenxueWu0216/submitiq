using Microsoft.AspNetCore.Mvc;
using SubmitIQ.Api.Contracts;
using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Services;

namespace SubmitIQ.Api.Controllers;

[ApiController]
[Route("review-queue")]
[Produces("application/json")]
public sealed class ReviewQueueController(ReviewService reviews) : ControllerBase
{
    public const int MaxPageSize = 100;

    /// <summary>Flagged fields waiting for (or resolved by) a reviewer, highest priority first.</summary>
    [HttpGet]
    [ProducesResponseType<PagedResult<ReviewTaskView>>(StatusCodes.Status200OK)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status400BadRequest)]
    public async Task<IActionResult> List([FromQuery] ReviewTaskStatus status = ReviewTaskStatus.Open,
                                          [FromQuery] int page = 1, [FromQuery(Name = "page_size")] int pageSize = 20,
                                          CancellationToken ct = default)
    {
        if (page < 1)
            ModelState.AddModelError("page", "must be 1 or greater");
        if (pageSize is < 1 or > MaxPageSize)
            ModelState.AddModelError("page_size", $"must be between 1 and {MaxPageSize}");
        if (!ModelState.IsValid)
            return ValidationProblem(ModelState);
        return Ok(await reviews.QueueAsync(status, page, pageSize, ct));
    }

    /// <summary>Confirm the flagged value or correct it. Writes an audit event.</summary>
    [HttpPost("{id:long}/resolve")]
    [ProducesResponseType<ResolveResult>(StatusCodes.Status200OK)]
    [ProducesResponseType<ValidationProblemDetails>(StatusCodes.Status400BadRequest)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status404NotFound)]
    [ProducesResponseType<ProblemDetails>(StatusCodes.Status409Conflict)]
    public async Task<IActionResult> Resolve(long id, ResolveRequest req, CancellationToken ct)
    {
        try
        {
            return Ok(await reviews.ResolveAsync(id, req, ct));
        }
        catch (NotFoundException e)
        {
            return Problem(statusCode: StatusCodes.Status404NotFound, title: "Review task not found", detail: e.Message);
        }
        catch (ConflictException e)
        {
            return Problem(statusCode: StatusCodes.Status409Conflict, title: "Review task cannot be resolved", detail: e.Message);
        }
        catch (InvalidValueException e)
        {
            return ValidationProblem(new ValidationProblemDetails(new Dictionary<string, string[]> { ["value"] = [e.Message] }));
        }
    }
}
