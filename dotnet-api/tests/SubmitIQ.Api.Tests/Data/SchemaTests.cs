using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Domain;
using SubmitIQ.Api.Tests.Infrastructure;

namespace SubmitIQ.Api.Tests.Data;

[Collection(SqlServerCollection.Name)]
public class SchemaTests(SqlServerFixture sql)
{
    [Fact]
    public async Task Migrations_cover_the_whole_model()
    {
        var cs = await sql.CreateDatabaseAsync("schema");
        await using var db = SqlServerFixture.CreateContext(cs);
        Assert.Empty(await db.Database.GetPendingMigrationsAsync());
        Assert.False(db.Database.HasPendingModelChanges(), "model changed without a migration: run dotnet ef migrations add");
    }

    [Fact]
    public async Task Stale_submission_update_is_rejected_by_the_rowversion()
    {
        var cs = await sql.CreateDatabaseAsync("concurrency");
        var now = DateTimeOffset.UtcNow;
        await using (var db = SqlServerFixture.CreateContext(cs))
        {
            db.Submissions.Add(new Submission { Id = "S1", Pipeline = "final", RecordJson = "{}", ReceivedAt = now, UpdatedAt = now });
            await db.SaveChangesAsync();
        }
        await using var reviewerA = SqlServerFixture.CreateContext(cs);
        await using var reviewerB = SqlServerFixture.CreateContext(cs);
        var a = await reviewerA.Submissions.SingleAsync();
        var b = await reviewerB.Submissions.SingleAsync();
        a.UpdatedAt = now.AddMinutes(1);
        await reviewerA.SaveChangesAsync();
        b.UpdatedAt = now.AddMinutes(2);   // B still holds the old rowversion
        await Assert.ThrowsAsync<DbUpdateConcurrencyException>(() => reviewerB.SaveChangesAsync());
    }

    [Fact]
    public async Task Submission_graph_round_trips_through_sql_server()
    {
        var cs = await sql.CreateDatabaseAsync("roundtrip");
        var now = DateTimeOffset.UtcNow;
        await using (var db = SqlServerFixture.CreateContext(cs))
        {
            db.Submissions.Add(new Submission
            {
                Id = "SUB-0003", Pipeline = "final", Status = SubmissionStatus.NeedsReview,
                InsuredName = "Summit Crest Precision Machining LLC", TotalTiv = 56_745_000m,
                EffectiveDate = new DateOnly(2027, 1, 1), RecordJson = "{}", ReceivedAt = now, UpdatedAt = now,
                Fields =
                [
                    new ExtractedField
                    {
                        Path = "totals.total_tiv", ValueJson = "56745000.0", Confidence = 0.95, Status = FieldStatus.Conflict,
                        IsCritical = true, Extractor = "derived", CitationDocument = "statement_of_values.xlsx",
                        CitationPage = null, CitationLocator = "sum of location TIV"
                    },
                ],
                Decisions =
                [
                    new Decision
                    {
                        Outcome = DecisionOutcome.Decline, Source = "rules-dotnet", RulesVersion = "2026-10-01", DecidedAt = now,
                        Reasons = [new DecisionReason { RuleId = "HURRICANE_ZONE", Outcome = DecisionOutcome.Decline,
                                                        Message = "frame in tier-1 zone", Fields = ["locations[2].zip"] }]
                    },
                ],
                ReviewTasks =
                [
                    new ReviewTask { FieldPath = "totals.total_tiv", FieldStatus = FieldStatus.Conflict, Reason = "SOV vs application",
                                     Priority = 100, Status = ReviewTaskStatus.Open, CreatedAt = now },
                ],
            });
            db.AuditEvents.Add(new AuditEvent { SubmissionId = "SUB-0003", EventType = AuditEventType.SubmissionIngested,
                                                Actor = "pipeline", OccurredAt = now });
            await db.SaveChangesAsync();
        }

        await using (var db = SqlServerFixture.CreateContext(cs))
        {
            var s = await db.Submissions.Include(x => x.Fields).Include(x => x.Decisions).Include(x => x.ReviewTasks)
                .SingleAsync(x => x.Id == "SUB-0003");
            Assert.Equal(56_745_000m, s.TotalTiv);
            Assert.Equal(new DateOnly(2027, 1, 1), s.EffectiveDate);
            Assert.NotEmpty(s.RowVersion);
            Assert.Equal(FieldStatus.Conflict, Assert.Single(s.Fields).Status);
            var reason = Assert.Single(Assert.Single(s.Decisions).Reasons);
            Assert.Equal(["locations[2].zip"], reason.Fields);
            Assert.Equal(ReviewTaskStatus.Open, Assert.Single(s.ReviewTasks).Status);
            Assert.Equal(1, await db.AuditEvents.CountAsync());
            // Enums are stored as readable strings, not integers.
            var status = await db.Database.SqlQuery<string>($"SELECT Status AS Value FROM Submissions").SingleAsync();
            Assert.Equal("NeedsReview", status);
        }
    }
}
