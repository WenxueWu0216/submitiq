-- The two queries EF Core 8 sends for GET /review-queue?status=open&page=N&page_size=20, copied from
-- the EF command log (ORIGINAL: FirstOrDefault field lookup) (Microsoft.EntityFrameworkCore.Database.Command). Run via perf/measure_sql.sh.
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
SELECT [t].[Id], [t].[CreatedAt], [t].[FieldPath], [t].[FieldStatus], [t].[Priority], [t].[Reason], [t].[Resolution], [t].[ResolvedAt], [t].[ResolvedBy], [t].[Status], [t].[SubmissionId], [s].[InsuredName], [t0].[Id], [t0].[CitationDocument], [t0].[CitationLocator], [t0].[CitationPage], [t0].[CitationSnippet], [t0].[Confidence], [t0].[Extractor], [t0].[IsCritical], [t0].[Path], [t0].[Status], [t0].[SubmissionId], [t0].[ValueJson]
FROM (
    SELECT [r].[Id], [r].[CreatedAt], [r].[FieldPath], [r].[FieldStatus], [r].[Priority], [r].[Reason], [r].[Resolution], [r].[ResolvedAt], [r].[ResolvedBy], [r].[Status], [r].[SubmissionId]
    FROM [ReviewTasks] AS [r]
    WHERE [r].[Status] = @status
    ORDER BY [r].[Priority] DESC, [r].[CreatedAt], [r].[Id]
    OFFSET @offset ROWS FETCH NEXT @fetch ROWS ONLY
) AS [t]
INNER JOIN [Submissions] AS [s] ON [t].[SubmissionId] = [s].[Id]
LEFT JOIN (
    SELECT [t1].[Id], [t1].[CitationDocument], [t1].[CitationLocator], [t1].[CitationPage], [t1].[CitationSnippet], [t1].[Confidence], [t1].[Extractor], [t1].[IsCritical], [t1].[Path], [t1].[Status], [t1].[SubmissionId], [t1].[ValueJson]
    FROM (
        SELECT [e].[Id], [e].[CitationDocument], [e].[CitationLocator], [e].[CitationPage], [e].[CitationSnippet], [e].[Confidence], [e].[Extractor], [e].[IsCritical], [e].[Path], [e].[Status], [e].[SubmissionId], [e].[ValueJson], ROW_NUMBER() OVER(PARTITION BY [e].[SubmissionId], [e].[Path] ORDER BY [e].[Id]) AS [row]
        FROM [ExtractedFields] AS [e]
    ) AS [t1]
    WHERE [t1].[row] <= 1
) AS [t0] ON [t].[SubmissionId] = [t0].[SubmissionId] AND [t].[FieldPath] = [t0].[Path]
ORDER BY [t].[Priority] DESC, [t].[CreatedAt], [t].[Id]
OPTION (RECOMPILE);   -- plan for this offset, not a cached one
SET STATISTICS XML OFF;
SET STATISTICS IO, TIME OFF;
