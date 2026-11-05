using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Data;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<SubmitIqDbContext>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("SubmitIQ"),
        sql => sql.EnableRetryOnFailure(maxRetryCount: 5)));   // Azure SQL serverless can be resuming
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.MapControllers();
app.Run();

public partial class Program;   // lets WebApplicationFactory<Program> find the entry point in tests
