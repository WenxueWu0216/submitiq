using System.Net;
using SubmitIQ.Api.Tests.Infrastructure;

namespace SubmitIQ.Api.Tests.Endpoints;

public class DecisionsEndpointTests(SqlServerFixture sql) : ApiTestBase(sql)
{
    [Fact]
    public async Task Returns_the_engine_decision_as_latest_with_the_pipeline_decision_in_history()
    {
        await PostSample("SUB-0003");
        var body = await Read(await Client.GetAsync("/decisions/SUB-0003"), HttpStatusCode.OK);

        var latest = body["latest"]!;
        Assert.Equal("rules-dotnet", latest["source"]!.GetValue<string>());
        Assert.Equal("decline", latest["outcome"]!.GetValue<string>());
        Assert.Equal("2026-10-01", latest["rules_version"]!.GetValue<string>());
        var reasons = latest["reasons"]!.AsArray();
        Assert.Equal(["ROOF_AGE", "HURRICANE_ZONE", "UNSPRINKLERED"], reasons.Select(r => r!["rule_id"]!.GetValue<string>()));
        Assert.Equal(["locations[2].zip", "locations[2].construction"],
                     reasons[1]!["fields"]!.AsArray().Select(f => f!.GetValue<string>()));

        var history = body["history"]!.AsArray();
        Assert.Equal(["rules-dotnet", "python-pipeline"], history.Select(h => h!["source"]!.GetValue<string>()));
    }

    [Fact]
    public async Task Unknown_submission_returns_404_problem()
    {
        await Problem(await Client.GetAsync("/decisions/NOPE"), HttpStatusCode.NotFound);
    }
}
