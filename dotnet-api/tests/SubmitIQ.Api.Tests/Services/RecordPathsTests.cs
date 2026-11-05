using System.Text.Json.Nodes;
using SubmitIQ.Api.Services;
using SubmitIQ.Api.Tests.Infrastructure;

namespace SubmitIQ.Api.Tests.Services;

public class RecordPathsTests
{
    private static JsonObject Record() => JsonNode.Parse("""
        {
          "submission_id": "S1",
          "insured": {"named_insured": "Acme LLC", "mailing_address": {"zip": "43215"}},
          "locations": [{"loc_number": 1, "tiv": 100.0}, {"loc_number": 3, "year_built": 1990}],
          "claims": [{"claim_number": "CMI-2023-00412", "paid": 5.0}],
          "loss_years": [{"policy_year": 2024, "earned_premium": 9.0}]
        }
        """)!.AsObject();

    [Theory]
    [InlineData("insured.named_insured", "\"Acme LLC\"")]
    [InlineData("insured.mailing_address.zip", "\"43215\"")]
    [InlineData("locations[3].year_built", "1990")]          // keyed by loc_number, not array position
    [InlineData("claims[CMI202300412].paid", "5.0")]          // keyed by the normalized claim number
    [InlineData("loss_years[2024].earned_premium", "9.0")]
    public void Get_resolves_paths_the_way_the_python_registry_keys_them(string path, string json)
    {
        Assert.Equal(json, RecordPaths.Get(Record(), path)!.ToJsonString());
    }

    [Theory]
    [InlineData("locations[2].tiv")]
    [InlineData("claims[NOPE].paid")]
    [InlineData("not a path")]
    public void Get_returns_null_for_paths_that_do_not_exist(string path)
    {
        Assert.Null(RecordPaths.Get(Record(), path));
    }

    [Fact]
    public void Set_writes_into_the_addressed_object_and_creates_missing_groups()
    {
        var rec = Record();
        Assert.True(RecordPaths.Set(rec, "locations[1].year_built", JsonValue.Create(2001)));
        Assert.True(RecordPaths.Set(rec, "coverage.deductible", JsonValue.Create(5000)));
        Assert.Equal(2001, rec["locations"]![0]!["year_built"]!.GetValue<int>());
        Assert.Equal(5000, rec["coverage"]!["deductible"]!.GetValue<int>());
    }

    [Fact]
    public void Set_refuses_a_location_that_is_not_on_the_record()
    {
        Assert.False(RecordPaths.Set(Record(), "locations[9].tiv", JsonValue.Create(1)));
    }

    [Fact]
    public void Every_field_path_in_the_sample_results_resolves_against_its_record()
    {
        // All provenance paths the Python pipeline produced must address something (or be a known-missing field).
        foreach (var file in Directory.GetFiles(Path.Combine(RepoPaths.Contracts, "pipeline_results"), "*.json"))
        {
            var doc = JsonNode.Parse(File.ReadAllText(file))!.AsObject();
            var record = doc["record"]!.AsObject();
            foreach (var (path, prov) in doc["provenance"]!.AsObject())
            {
                var value = RecordPaths.Get(record, path);
                if (prov!["status"]!.GetValue<string>() != "missing")
                    Assert.True(value is not null, $"{Path.GetFileName(file)}: {path} did not resolve");
            }
        }
    }

    [Theory]
    [InlineData("locations[12].year_built", "locations[].year_built")]
    [InlineData("insured.fein", "insured.fein")]
    public void Registry_generic_path(string path, string generic)
    {
        Assert.Equal(generic, FieldRegistry.Generic(path));
        var registry = FieldRegistry.Load(Path.Combine(RepoPaths.Contracts, "field_registry.json"));
        Assert.NotNull(registry.Find(path));
    }
}
