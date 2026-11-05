using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace SubmitIQ.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddReviewQueueIndex : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateIndex(
                name: "IX_ReviewTasks_Status_Priority_CreatedAt_Id",
                table: "ReviewTasks",
                columns: new[] { "Status", "Priority", "CreatedAt", "Id" },
                descending: new[] { false, true, false, false });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_ReviewTasks_Status_Priority_CreatedAt_Id",
                table: "ReviewTasks");
        }
    }
}
