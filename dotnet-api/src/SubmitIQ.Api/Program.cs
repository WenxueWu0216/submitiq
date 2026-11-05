using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Mvc.ModelBinding.Metadata;
using Microsoft.EntityFrameworkCore;
using SubmitIQ.Api.Data;
using SubmitIQ.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddDbContext<SubmitIqDbContext>(o =>
    o.UseSqlServer(builder.Configuration.GetConnectionString("SubmitIQ"),
        sql => sql.EnableRetryOnFailure(maxRetryCount: 5)));   // Azure SQL serverless can be resuming

// snake_case on the wire, like the Python pipeline's JSON (needs_review, low_confidence, ...)
builder.Services.AddControllers(o =>
{
    // Validation error keys use the wire names ("submission_id"), not the C# names ("SubmissionId").
    o.ModelMetadataDetailsProviders.Add(new SystemTextJsonValidationMetadataProvider(JsonNamingPolicy.SnakeCaseLower));
    // An unparseable body already reports where it failed; skip the extra "the dto field is required".
    o.SuppressImplicitRequiredAttributeForNonNullableReferenceTypes = true;
}).AddJsonOptions(o =>
{
    o.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower;
    o.JsonSerializerOptions.DictionaryKeyPolicy = null;   // keep field paths as sent
    o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower));
    o.AllowInputFormatterExceptionMessages = false;       // do not echo .NET type names back to callers
});
builder.Services.AddProblemDetails();   // RFC 7807 bodies for every error, including unhandled exceptions
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton(_ => FieldRegistry.Load(
    builder.Configuration["FieldRegistryPath"] ?? Path.Combine(AppContext.BaseDirectory, "contracts", "field_registry.json")));
builder.Services.AddScoped<IngestService>();
builder.Services.AddScoped<ReviewService>();

var app = builder.Build();

app.UseExceptionHandler();
app.UseStatusCodePages();
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.MapControllers();
app.Run();

public partial class Program;   // lets WebApplicationFactory<Program> find the entry point in tests
