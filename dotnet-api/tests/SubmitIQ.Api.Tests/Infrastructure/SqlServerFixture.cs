using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Data;
using Testcontainers.MsSql;

namespace SubmitIQ.Api.Tests.Infrastructure;

/// <summary>
/// One real SQL Server 2022 container for the whole test run (Testcontainers).
/// Each test class gets its own database, so tests never see each other's rows.
/// </summary>
public sealed class SqlServerFixture : IAsyncLifetime
{
    private readonly MsSqlContainer _container = new MsSqlBuilder("mcr.microsoft.com/mssql/server:2022-latest").Build();

    public Task InitializeAsync() => _container.StartAsync();

    public Task DisposeAsync() => _container.DisposeAsync().AsTask();

    /// <summary>Connection string for a fresh, fully migrated database.</summary>
    public async Task<string> CreateDatabaseAsync(string name)
    {
        var cs = new Microsoft.Data.SqlClient.SqlConnectionStringBuilder(_container.GetConnectionString())
        {
            InitialCatalog = $"{name}_{Guid.NewGuid():N}"[..Math.Min(100, name.Length + 33)]
        }.ConnectionString;
        await using var db = CreateContext(cs);
        await db.Database.MigrateAsync();
        return cs;
    }

    public static SubmitIqDbContext CreateContext(string connectionString) =>
        new(new DbContextOptionsBuilder<SubmitIqDbContext>().UseSqlServer(connectionString).Options);
}

[CollectionDefinition(Name)]
public sealed class SqlServerCollection : ICollectionFixture<SqlServerFixture>
{
    public const string Name = "sqlserver";
}
