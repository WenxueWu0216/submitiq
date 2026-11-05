using System.Net;
using System.Net.Http.Json;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Tests.Infrastructure;

namespace SubmitIQ.Api.Tests.Endpoints;

public class SubmissionsEndpointTests(SqlServerFixture sql) : ApiTestBase(sql)
{
    [Fact]
    public async Task Post_ingests_a_pipeline_result_and_returns_201_with_location()
    {
        var resp = await Client.PostAsJsonAsync("/submissions", Sample("SUB-0038"));
        var body = await Read(resp, HttpStatusCode.Created);

        Assert.Equal("/submissions/SUB-0038", resp.Headers.Location!.AbsolutePath);
        Assert.Equal("needs_review", body["status"]!.GetValue<string>());
        var provenance = Sample("SUB-0038")["provenance"]!.AsObject();
        Assert.Equal(provenance.Count, body["fields"]!.GetValue<int>());
        var flagged = provenance.Count(kv => kv.Value!["status"]!.GetValue<string>() != "ok");
        Assert.Equal(flagged, body["review_tasks_created"]!.GetValue<int>());
        Assert.Equal("refer", body["decision"]!.GetValue<string>());
        Assert.Equal("refer", body["pipeline_decision"]!.GetValue<string>());

        await using var db = Db();
        Assert.Equal(flagged, await db.ReviewTasks.CountAsync(t => t.SubmissionId == "SUB-0038" && t.Status == ReviewTaskStatus.Open));
        var audit = await db.AuditEvents.SingleAsync();
        Assert.Equal(AuditEventType.SubmissionIngested, audit.EventType);
    }

    [Fact]
    public async Task Post_clean_submission_is_auto_cleared_with_no_review_tasks()
    {
        var body = await PostSample("SUB-0010");
        Assert.Equal("auto_cleared", body["status"]!.GetValue<string>());
        Assert.Equal(0, body["review_tasks_created"]!.GetValue<int>());
        Assert.Equal("accept", body["decision"]!.GetValue<string>());
    }

    [Fact]
    public async Task Post_same_submission_twice_returns_409_problem()
    {
        await PostSample("SUB-0003");
        var problem = await Problem(await Client.PostAsJsonAsync("/submissions", Sample("SUB-0003")), HttpStatusCode.Conflict);
        Assert.Contains("SUB-0003", problem["detail"]!.GetValue<string>());
    }

    [Fact]
    public async Task Post_with_bad_id_and_no_record_returns_400_with_snake_case_keys()
    {
        var doc = Sample("SUB-0010");
        doc["submission_id"] = "bad id!";
        doc.Remove("record");
        var problem = await Problem(await Client.PostAsJsonAsync("/submissions", doc), HttpStatusCode.BadRequest);
        Assert.Equal(["record", "submission_id"], ErrorKeys(problem));
    }

    [Fact]
    public async Task Post_with_mismatched_record_id_and_unknown_field_path_returns_400()
    {
        var doc = Sample("SUB-0010");
        doc["submission_id"] = "SUB-OTHER";
        doc["provenance"]!["not.a_field"] = new JsonObject { ["path"] = "not.a_field", ["status"] = "ok" };
        var problem = await Problem(await Client.PostAsJsonAsync("/submissions", doc), HttpStatusCode.BadRequest);
        Assert.Equal(["provenance.not.a_field", "record.submission_id"], ErrorKeys(problem));
    }

    [Fact]
    public async Task Post_with_invalid_enum_returns_400_without_leaking_type_names()
    {
        var doc = Sample("SUB-0010");
        doc["provenance"]!.AsObject().First().Value!["status"] = "maybe";
        var resp = await Client.PostAsJsonAsync("/submissions", doc);
        var text = (await Problem(resp, HttpStatusCode.BadRequest)).ToJsonString();
        Assert.Contains("provenance", text);
        Assert.DoesNotContain("System.", text);
        Assert.DoesNotContain("SubmitIQ.Api", text);
    }

    [Fact]
    public async Task Post_rejects_out_of_range_confidence()
    {
        var doc = Sample("SUB-0010");
        doc["provenance"]!.AsObject().First().Value!["confidence"] = 1.5;
        await Problem(await Client.PostAsJsonAsync("/submissions", doc), HttpStatusCode.BadRequest);
    }

    [Fact]
    public async Task Get_returns_fields_with_page_citations_and_the_latest_decision()
    {
        await PostSample("SUB-0003");
        var body = await Read(await Client.GetAsync("/submissions/SUB-0003"), HttpStatusCode.OK);

        Assert.Equal("Summit Crest Precision Machining LLC", body["insured_name"]!.GetValue<string>());
        Assert.Equal(56_745_000m, body["total_tiv"]!.GetValue<decimal>());
        Assert.Equal("2027-01-01", body["effective_date"]!.GetValue<string>());
        Assert.Equal(1, body["open_review_tasks"]!.GetValue<int>());
        var latest = body["latest_decision"]!;
        Assert.Equal("rules-dotnet", latest["source"]!.GetValue<string>());
        Assert.Equal("decline", latest["outcome"]!.GetValue<string>());

        var fields = body["fields"]!.AsArray().Select(f => f!.AsObject()).ToList();
        var name = fields.Single(f => f["path"]!.GetValue<string>() == "insured.named_insured");
        Assert.Equal("Summit Crest Precision Machining LLC", name["value"]!.GetValue<string>());
        Assert.True(name["is_critical"]!.GetValue<bool>());
        Assert.Equal("Signed_App.pdf", name["citation"]!["document"]!.GetValue<string>());
        Assert.Equal(1, name["citation"]!["page"]!.GetValue<int>());
        var tiv = fields.Single(f => f["path"]!.GetValue<string>() == "totals.total_tiv");
        Assert.Equal("conflict", tiv["status"]!.GetValue<string>());
    }

    [Fact]
    public async Task Get_unknown_submission_returns_404_problem()
    {
        var problem = await Problem(await Client.GetAsync("/submissions/NOPE"), HttpStatusCode.NotFound);
        Assert.Contains("NOPE", problem["detail"]!.GetValue<string>());
    }
}
