using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using SubmitIQ.Api.Data;

namespace SubmitIQ.Api.Tests.Infrastructure;

/// <summary>
/// The real API (WebApplicationFactory) on a real SQL Server (Testcontainers). xUnit creates a new
/// instance per test, so every test gets its own freshly migrated database.
/// </summary>
[Collection(SqlServerCollection.Name)]
public abstract class ApiTestBase(SqlServerFixture sql) : IAsyncLifetime
{
    private WebApplicationFactory<Program>? _factory;
    protected HttpClient Client { get; private set; } = null!;
    protected string ConnectionString { get; private set; } = "";

    public async Task InitializeAsync()
    {
        ConnectionString = await sql.CreateDatabaseAsync(GetType().Name);
        _factory = new WebApplicationFactory<Program>().WithWebHostBuilder(b =>
        {
            b.UseEnvironment("Testing");
            b.ConfigureServices(services =>
            {
                services.RemoveAll<DbContextOptions<SubmitIqDbContext>>();
                services.AddDbContext<SubmitIqDbContext>(o => o.UseSqlServer(ConnectionString));
            });
        });
        Client = _factory.CreateClient();
    }

    public async Task DisposeAsync()
    {
        Client.Dispose();
        if (_factory is not null)
            await _factory.DisposeAsync();
    }

    protected SubmitIqDbContext Db() => SqlServerFixture.CreateContext(ConnectionString);

    /// <summary>A real PipelineResult exported from the Python pipeline (dotnet-api/contracts/pipeline_results).</summary>
    protected static JsonObject Sample(string id) =>
        JsonNode.Parse(File.ReadAllText(Path.Combine(RepoPaths.Contracts, "pipeline_results", id + ".json")))!.AsObject();

    protected async Task<JsonObject> PostSample(string id, HttpStatusCode expected = HttpStatusCode.Created)
    {
        var resp = await Client.PostAsJsonAsync("/submissions", Sample(id));
        return await Read(resp, expected);
    }

    protected static async Task<JsonObject> Read(HttpResponseMessage resp, HttpStatusCode expected)
    {
        var text = await resp.Content.ReadAsStringAsync();
        Assert.True(resp.StatusCode == expected, $"expected {(int)expected}, got {(int)resp.StatusCode}: {text}");
        return JsonNode.Parse(text)!.AsObject();
    }

    /// <summary>Asserts an RFC 7807 problem response and returns its body.</summary>
    protected static async Task<JsonObject> Problem(HttpResponseMessage resp, HttpStatusCode expected)
    {
        Assert.Equal("application/problem+json", resp.Content.Headers.ContentType?.MediaType);
        var body = await Read(resp, expected);
        Assert.Equal((int)expected, body["status"]!.GetValue<int>());
        Assert.False(string.IsNullOrEmpty(body["title"]?.GetValue<string>()));
        return body;
    }

    protected static string[] ErrorKeys(JsonObject problem) =>
        problem["errors"]!.AsObject().Select(kv => kv.Key).Order(StringComparer.Ordinal).ToArray();

    protected static JsonSerializerOptions Json { get; } = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower };
}
