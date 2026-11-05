using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace SubmitIQ.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "AuditEvents",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    SubmissionId = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    ReviewTaskId = table.Column<long>(type: "bigint", nullable: true),
                    EventType = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    Actor = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: false),
                    FieldPath = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: true),
                    OldValueJson = table.Column<string>(type: "nvarchar(2000)", maxLength: 2000, nullable: true),
                    NewValueJson = table.Column<string>(type: "nvarchar(2000)", maxLength: 2000, nullable: true),
                    Comment = table.Column<string>(type: "nvarchar(1000)", maxLength: 1000, nullable: true),
                    OccurredAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_AuditEvents", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Submissions",
                columns: table => new
                {
                    Id = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Pipeline = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Status = table.Column<string>(type: "nvarchar(16)", maxLength: 16, nullable: false),
                    InsuredName = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: true),
                    TotalTiv = table.Column<decimal>(type: "decimal(18,2)", precision: 18, scale: 2, nullable: true),
                    EffectiveDate = table.Column<DateOnly>(type: "date", nullable: true),
                    RecordJson = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    ReceivedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    UpdatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    RowVersion = table.Column<byte[]>(type: "rowversion", rowVersion: true, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Submissions", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Decisions",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    SubmissionId = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Outcome = table.Column<string>(type: "nvarchar(8)", maxLength: 8, nullable: false),
                    Source = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    RulesVersion = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    DecidedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    Reasons = table.Column<string>(type: "nvarchar(max)", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Decisions", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Decisions_Submissions_SubmissionId",
                        column: x => x.SubmissionId,
                        principalTable: "Submissions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ExtractedFields",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    SubmissionId = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    Path = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                    ValueJson = table.Column<string>(type: "nvarchar(2000)", maxLength: 2000, nullable: true),
                    Confidence = table.Column<double>(type: "float", nullable: true),
                    Status = table.Column<string>(type: "nvarchar(16)", maxLength: 16, nullable: false),
                    IsCritical = table.Column<bool>(type: "bit", nullable: false),
                    Extractor = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: true),
                    CitationDocument = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: true),
                    CitationPage = table.Column<int>(type: "int", nullable: true),
                    CitationLocator = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: true),
                    CitationSnippet = table.Column<string>(type: "nvarchar(500)", maxLength: 500, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ExtractedFields", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ExtractedFields_Submissions_SubmissionId",
                        column: x => x.SubmissionId,
                        principalTable: "Submissions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ReviewTasks",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    SubmissionId = table.Column<string>(type: "nvarchar(64)", maxLength: 64, nullable: false),
                    FieldPath = table.Column<string>(type: "nvarchar(256)", maxLength: 256, nullable: false),
                    FieldStatus = table.Column<string>(type: "nvarchar(16)", maxLength: 16, nullable: false),
                    Reason = table.Column<string>(type: "nvarchar(1000)", maxLength: 1000, nullable: false),
                    Priority = table.Column<int>(type: "int", nullable: false),
                    Status = table.Column<string>(type: "nvarchar(16)", maxLength: 16, nullable: false),
                    CreatedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: false),
                    ResolvedAt = table.Column<DateTimeOffset>(type: "datetimeoffset", nullable: true),
                    ResolvedBy = table.Column<string>(type: "nvarchar(128)", maxLength: 128, nullable: true),
                    Resolution = table.Column<string>(type: "nvarchar(16)", maxLength: 16, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ReviewTasks", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ReviewTasks_Submissions_SubmissionId",
                        column: x => x.SubmissionId,
                        principalTable: "Submissions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_AuditEvents_SubmissionId",
                table: "AuditEvents",
                column: "SubmissionId");

            migrationBuilder.CreateIndex(
                name: "IX_Decisions_SubmissionId_DecidedAt",
                table: "Decisions",
                columns: new[] { "SubmissionId", "DecidedAt" });

            migrationBuilder.CreateIndex(
                name: "IX_ExtractedFields_SubmissionId_Path",
                table: "ExtractedFields",
                columns: new[] { "SubmissionId", "Path" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_ReviewTasks_SubmissionId",
                table: "ReviewTasks",
                column: "SubmissionId");

            migrationBuilder.CreateIndex(
                name: "IX_Submissions_Status",
                table: "Submissions",
                column: "Status");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "AuditEvents");

            migrationBuilder.DropTable(
                name: "Decisions");

            migrationBuilder.DropTable(
                name: "ExtractedFields");

            migrationBuilder.DropTable(
                name: "ReviewTasks");

            migrationBuilder.DropTable(
                name: "Submissions");
        }
    }
}
