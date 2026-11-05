-- The two queries EF Core 8 sends for GET /review-queue?status=open&page=N&page_size=20, copied from
-- the EF command log (Microsoft.EntityFrameworkCore.Database.Command). Run via perf/measure_sql.sh.
SET NOCOUNT ON;
DECLARE @status nvarchar(16) = N'Open', @offset int = $(Offset), @fetch int = 20;

-- warm-up (buffer pool), not measured
SELECT COUNT(*) FROM [ReviewTasks] AS [r] WHERE [r].[Status] = @status;

PRINT '=== COUNT query ===';
SET STATISTICS IO, TIME ON;
SELECT COUNT(*) AS open_tasks FROM [ReviewTasks] AS [r] WHERE [r].[Status] = @status;
SET STATISTICS IO, TIME OFF;

PRINT '=== page query ===';
SET STATISTICS IO, TIME ON;
SET STATISTICS XML ON;
SELECT [t].[Id], [t].[CreatedAt], [t].[FieldPath], [t].[FieldStatus], [t].[Priority], [t].[Reason], [t].[Resolution], [t].[ResolvedAt], [t].[ResolvedBy], [t].[Status], [t].[SubmissionId], [s].[InsuredName], [e].[Id], [e].[CitationDocument], [e].[CitationLocator], [e].[CitationPage], [e].[CitationSnippet], [e].[Confidence], [e].[Extractor], [e].[IsCritical], [e].[Path], [e].[Status], [e].[SubmissionId], [e].[ValueJson]
FROM (
    SELECT [r].[Id], [r].[CreatedAt], [r].[FieldPath], [r].[FieldStatus], [r].[Priority], [r].[Reason], [r].[Resolution], [r].[ResolvedAt], [r].[ResolvedBy], [r].[Status], [r].[SubmissionId]
    FROM [ReviewTasks] AS [r]
    WHERE [r].[Status] = @status
    ORDER BY [r].[Priority] DESC, [r].[CreatedAt], [r].[Id]
    OFFSET @offset ROWS FETCH NEXT @fetch ROWS ONLY
) AS [t]
LEFT JOIN [ExtractedFields] AS [e] ON [t].[SubmissionId] = [e].[SubmissionId] AND [t].[FieldPath] = [e].[Path]
INNER JOIN [Submissions] AS [s] ON [t].[SubmissionId] = [s].[Id]
ORDER BY [t].[Priority] DESC, [t].[CreatedAt], [t].[Id]
OPTION (RECOMPILE);   -- plan for this offset, not a cached one
SET STATISTICS XML OFF;
SET STATISTICS IO, TIME OFF;
