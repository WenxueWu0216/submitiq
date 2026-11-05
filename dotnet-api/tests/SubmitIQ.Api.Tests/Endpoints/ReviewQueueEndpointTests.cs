using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Tests.Infrastructure;

namespace SubmitIQ.Api.Tests.Endpoints;

public class ReviewQueueEndpointTests(SqlServerFixture sql) : ApiTestBase(sql)
{
    private async Task<List<JsonObject>> OpenTasks(string query = "page_size=100")
    {
        var body = await Read(await Client.GetAsync($"/review-queue?{query}"), HttpStatusCode.OK);
        return body["items"]!.AsArray().Select(i => i!.AsObject()).ToList();
    }

    private async Task<JsonObject> Task(string submissionId, string fieldPath) =>
        (await OpenTasks()).Single(t => t["submission_id"]!.GetValue<string>() == submissionId
                                        && t["field_path"]!.GetValue<string>() == fieldPath);

    private Task<HttpResponseMessage> Resolve(long id, object body) => Client.PostAsJsonAsync($"/review-queue/{id}/resolve", body);

    // ------------------------------------------------------------------ GET /review-queue

    [Fact]
    public async Task Queue_lists_open_tasks_highest_priority_first()
    {
        await PostSample("SUB-0038");
        await PostSample("SUB-0059");
        var items = await OpenTasks();
        Assert.Equal(9 + 14, items.Count);
        var priorities = items.Select(i => i["priority"]!.GetValue<int>()).ToList();
        Assert.Equal(priorities.OrderDescending(), priorities);
        Assert.All(items, i => Assert.Equal("open", i["status"]!.GetValue<string>()));
        var top = items[0];
        Assert.True(top["is_critical"]!.GetValue<bool>());
        Assert.NotNull(top["citation"]);
    }

    [Fact]
    public async Task Queue_pages_without_overlap()
    {
        await PostSample("SUB-0059");
        var p1 = await Read(await Client.GetAsync("/review-queue?page=1&page_size=5"), HttpStatusCode.OK);
        var p3 = await Read(await Client.GetAsync("/review-queue?page=3&page_size=5"), HttpStatusCode.OK);
        Assert.Equal(14, p1["total_count"]!.GetValue<int>());
        Assert.Equal(3, p1["total_pages"]!.GetValue<int>());
        Assert.Equal(5, p1["items"]!.AsArray().Count);
        Assert.Equal(4, p3["items"]!.AsArray().Count);
        var ids1 = p1["items"]!.AsArray().Select(i => i!["id"]!.GetValue<long>());
        var ids3 = p3["items"]!.AsArray().Select(i => i!["id"]!.GetValue<long>());
        Assert.Empty(ids1.Intersect(ids3));
    }

    [Theory]
    [InlineData("page=0", "page")]
    [InlineData("page_size=0", "page_size")]
    [InlineData("page_size=101", "page_size")]
    [InlineData("status=bogus", "status")]
    public async Task Queue_rejects_bad_query_parameters(string query, string key)
    {
        var problem = await Problem(await Client.GetAsync($"/review-queue?{query}"), HttpStatusCode.BadRequest);
        Assert.Equal([key], ErrorKeys(problem));
    }

    [Fact]
    public async Task Queue_filters_by_status()
    {
        await PostSample("SUB-0003");
        var task = (await OpenTasks()).Single();
        await Read(await Resolve(task["id"]!.GetValue<long>(), new { reviewer = "uw1", action = "confirm" }), HttpStatusCode.OK);
        Assert.Empty(await OpenTasks());
        var resolved = await OpenTasks("status=resolved");
        Assert.Equal("confirmed", Assert.Single(resolved)["resolution"]!.GetValue<string>());
    }

    // ------------------------------------------------------------------ POST /review-queue/{id}/resolve

    [Fact]
    public async Task Confirm_resolves_the_task_and_writes_an_audit_event()
    {
        await PostSample("SUB-0003");
        var task = await Task("SUB-0003", "totals.total_tiv");
        var body = await Read(await Resolve(task["id"]!.GetValue<long>(), new { reviewer = "uw1", action = "confirm", comment = "SOV is current" }),
                              HttpStatusCode.OK);
        Assert.Equal("resolved", body["task"]!["status"]!.GetValue<string>());
        Assert.Equal("approved", body["submission_status"]!.GetValue<string>());   // it was the only open task
        Assert.Equal(0, body["open_review_tasks"]!.GetValue<int>());

        await using var db = Db();
        var field = await db.ExtractedFields.SingleAsync(f => f.SubmissionId == "SUB-0003" && f.Path == "totals.total_tiv");
        Assert.Equal(FieldStatus.Ok, field.Status);
        Assert.Equal("56745000.0", field.ValueJson);   // value unchanged
        var audit = await db.AuditEvents.SingleAsync(a => a.EventType == AuditEventType.FieldConfirmed);
        Assert.Equal(("uw1", "totals.total_tiv", "SOV is current"), (audit.Actor, audit.FieldPath, audit.Comment));
    }

    [Fact]
    public async Task Correct_updates_the_value_and_records_old_and_new_in_the_audit_trail()
    {
        await PostSample("SUB-0038");
        var task = await Task("SUB-0038", "locations[3].year_built");
        var body = await Read(await Resolve(task["id"]!.GetValue<long>(), new { reviewer = "uw2", action = "correct", value = 1996 }),
                              HttpStatusCode.OK);
        Assert.Equal("corrected", body["task"]!["resolution"]!.GetValue<string>());
        Assert.Equal(1996, body["task"]!["current_value"]!.GetValue<int>());
        Assert.Equal("needs_review", body["submission_status"]!.GetValue<string>());

        var sub = await Read(await Client.GetAsync("/submissions/SUB-0038"), HttpStatusCode.OK);
        var f = sub["fields"]!.AsArray().Single(x => x!["path"]!.GetValue<string>() == "locations[3].year_built")!;
        Assert.Equal(1996, f["value"]!.GetValue<int>());
        Assert.Equal("human:uw2", f["extractor"]!.GetValue<string>());
        Assert.Equal(1.0, f["confidence"]!.GetValue<double>());

        await using var db = Db();
        var audit = await db.AuditEvents.SingleAsync(a => a.EventType == AuditEventType.FieldCorrected);
        Assert.Equal(("1998", "1996"), (audit.OldValueJson, audit.NewValueJson));
        var record = JsonNode.Parse((await db.Submissions.SingleAsync()).RecordJson)!;
        Assert.Equal(1996, record["locations"]!.AsArray().Single(l => l!["loc_number"]!.GetValue<int>() == 3)!["year_built"]!.GetValue<int>());
    }

    [Fact]
    public async Task Correcting_a_missing_required_field_re_runs_the_rules_and_logs_the_decision_change()
    {
        await PostSample("SUB-0038");   // referred only because locations[1].year_built is missing
        var task = await Task("SUB-0038", "locations[1].year_built");
        var body = await Read(await Resolve(task["id"]!.GetValue<long>(), new { reviewer = "uw1", action = "correct", value = 1996 }),
                              HttpStatusCode.OK);
        Assert.Equal("accept", body["decision"]!.GetValue<string>());

        await using var db = Db();
        var events = await db.AuditEvents.Where(a => a.EventType != AuditEventType.SubmissionIngested).OrderBy(a => a.Id).ToListAsync();
        Assert.Equal([AuditEventType.FieldCorrected, AuditEventType.DecisionMade], events.Select(e => e.EventType));
        Assert.Equal(("\"refer\"", "\"accept\""), (events[1].OldValueJson, events[1].NewValueJson));
    }

    [Theory]
    [InlineData("locations[1].year_built", "{\"reviewer\":\"uw1\",\"action\":\"correct\"}")]                     // value omitted
    [InlineData("locations[1].year_built", "{\"reviewer\":\"uw1\",\"action\":\"correct\",\"value\":\"1990\"}")] // string for an int
    [InlineData("locations[1].year_built", "{\"reviewer\":\"uw1\",\"action\":\"correct\",\"value\":1990.5}")]   // not an integer
    [InlineData("locations[1].tiv", "{\"reviewer\":\"uw1\",\"action\":\"correct\",\"value\":-5}")]              // negative money
    public async Task Correct_rejects_values_of_the_wrong_kind(string field, string json)
    {
        await PostSample("SUB-0038");
        var task = await Task("SUB-0038", field);
        var resp = await Client.PostAsync($"/review-queue/{task["id"]}/resolve",
                                          new StringContent(json, System.Text.Encoding.UTF8, "application/json"));
        Assert.Equal(["value"], ErrorKeys(await Problem(resp, HttpStatusCode.BadRequest)));
        await using var db = Db();
        Assert.Equal(ReviewTaskStatus.Open, (await db.ReviewTasks.SingleAsync(t => t.Id == task["id"]!.GetValue<long>())).Status);
    }

    [Fact]
    public async Task Correct_with_explicit_null_clears_the_field()
    {
        await PostSample("SUB-0038");
        var task = await Task("SUB-0038", "locations[3].year_built");
        var resp = await Client.PostAsync($"/review-queue/{task["id"]}/resolve",
            new StringContent("{\"reviewer\":\"uw1\",\"action\":\"correct\",\"value\":null}", System.Text.Encoding.UTF8, "application/json"));
        var body = await Read(resp, HttpStatusCode.OK);
        Assert.Null(body["task"]!["current_value"]);
    }

    [Fact]
    public async Task Resolving_twice_returns_409()
    {
        await PostSample("SUB-0003");
        var id = (await OpenTasks()).Single()["id"]!.GetValue<long>();
        await Read(await Resolve(id, new { reviewer = "uw1", action = "confirm" }), HttpStatusCode.OK);
        var problem = await Problem(await Resolve(id, new { reviewer = "uw2", action = "confirm" }), HttpStatusCode.Conflict);
        Assert.Contains("uw1", problem["detail"]!.GetValue<string>());
    }

    [Fact]
    public async Task Resolving_an_unknown_task_returns_404()
    {
        await Problem(await Resolve(424242, new { reviewer = "uw1", action = "confirm" }), HttpStatusCode.NotFound);
    }

    [Theory]
    [InlineData("{\"action\":\"confirm\"}", "reviewer")]
    [InlineData("{\"reviewer\":\"uw1\"}", "action")]
    [InlineData("{\"reviewer\":\"uw1\",\"action\":\"delete\"}", "$.action")]
    public async Task Resolve_validates_the_request(string json, string key)
    {
        await PostSample("SUB-0003");
        var id = (await OpenTasks()).Single()["id"]!.GetValue<long>();
        var resp = await Client.PostAsync($"/review-queue/{id}/resolve", new StringContent(json, System.Text.Encoding.UTF8, "application/json"));
        Assert.Contains(key, ErrorKeys(await Problem(resp, HttpStatusCode.BadRequest)));
    }
}
