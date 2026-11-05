using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Domain;

namespace SubmitIQ.Api.Data;

public class SubmitIqDbContext(DbContextOptions<SubmitIqDbContext> options) : DbContext(options)
{
    public DbSet<Submission> Submissions => Set<Submission>();
    public DbSet<ExtractedField> ExtractedFields => Set<ExtractedField>();
    public DbSet<Decision> Decisions => Set<Decision>();
    public DbSet<ReviewTask> ReviewTasks => Set<ReviewTask>();
    public DbSet<AuditEvent> AuditEvents => Set<AuditEvent>();

    protected override void ConfigureConventions(ModelConfigurationBuilder b)
    {
        b.Properties<SubmissionStatus>().HaveConversion<string>().HaveMaxLength(16);
        b.Properties<FieldStatus>().HaveConversion<string>().HaveMaxLength(16);
        b.Properties<DecisionOutcome>().HaveConversion<string>().HaveMaxLength(8);
        b.Properties<ReviewTaskStatus>().HaveConversion<string>().HaveMaxLength(16);
        b.Properties<ReviewResolution>().HaveConversion<string>().HaveMaxLength(16);
        b.Properties<AuditEventType>().HaveConversion<string>().HaveMaxLength(32);
    }

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Submission>(e =>
        {
            e.Property(x => x.Id).HasMaxLength(64);
            e.Property(x => x.Pipeline).HasMaxLength(64);
            e.Property(x => x.InsuredName).HasMaxLength(256);
            e.Property(x => x.TotalTiv).HasPrecision(18, 2);
            e.Property(x => x.RowVersion).IsRowVersion();
            e.HasMany(x => x.Fields).WithOne(f => f.Submission).HasForeignKey(f => f.SubmissionId).OnDelete(DeleteBehavior.Cascade);
            e.HasMany(x => x.Decisions).WithOne(d => d.Submission).HasForeignKey(d => d.SubmissionId).OnDelete(DeleteBehavior.Cascade);
            e.HasMany(x => x.ReviewTasks).WithOne(t => t.Submission).HasForeignKey(t => t.SubmissionId).OnDelete(DeleteBehavior.Cascade);
            e.HasIndex(x => x.Status);
        });

        b.Entity<ExtractedField>(e =>
        {
            e.Property(x => x.SubmissionId).HasMaxLength(64);
            e.Property(x => x.Path).HasMaxLength(256);
            e.Property(x => x.ValueJson).HasMaxLength(2000);
            e.Property(x => x.Extractor).HasMaxLength(64);
            e.Property(x => x.CitationDocument).HasMaxLength(256);
            e.Property(x => x.CitationLocator).HasMaxLength(128);
            e.Property(x => x.CitationSnippet).HasMaxLength(500);
            e.HasIndex(x => new { x.SubmissionId, x.Path }).IsUnique();
        });

        b.Entity<Decision>(e =>
        {
            e.Property(x => x.SubmissionId).HasMaxLength(64);
            e.Property(x => x.Source).HasMaxLength(32);
            e.Property(x => x.RulesVersion).HasMaxLength(32);
            e.OwnsMany(x => x.Reasons, r => r.ToJson());   // SQL Server JSON column (EF Core 8)
            e.HasIndex(x => new { x.SubmissionId, x.DecidedAt });
        });

        b.Entity<ReviewTask>(e =>
        {
            e.Property(x => x.SubmissionId).HasMaxLength(64);
            e.Property(x => x.FieldPath).HasMaxLength(256);
            e.Property(x => x.Reason).HasMaxLength(1000);
            e.Property(x => x.ResolvedBy).HasMaxLength(128);
            // Serves GET /review-queue: WHERE Status = @s ORDER BY Priority DESC, CreatedAt, Id OFFSET/FETCH,
            // and its COUNT. Measured in perf/README.md (1M tasks: COUNT 29,847 -> 252 logical reads).
            e.HasIndex(x => new { x.Status, x.Priority, x.CreatedAt, x.Id })
                .IsDescending(false, true, false, false)
                .HasDatabaseName("IX_ReviewTasks_Status_Priority_CreatedAt_Id");
        });

        b.Entity<AuditEvent>(e =>
        {
            e.Property(x => x.SubmissionId).HasMaxLength(64);
            e.Property(x => x.Actor).HasMaxLength(128);
            e.Property(x => x.FieldPath).HasMaxLength(256);
            e.Property(x => x.OldValueJson).HasMaxLength(2000);
            e.Property(x => x.NewValueJson).HasMaxLength(2000);
            e.Property(x => x.Comment).HasMaxLength(1000);
            e.HasIndex(x => x.SubmissionId);
        });
    }
}
