-- Seeds a large synthetic review queue for the GET /review-queue benchmark (perf/README.md).
--   sqlcmd -d SubmitIQ_Perf -v Submissions=100000 TasksPerSubmission=10 OpenPercent=5 -i perf/seed.sql
-- Deterministic: values derive from row numbers, so every run produces the same data.
SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @subs int = $(Submissions);
DECLARE @per int = $(TasksPerSubmission);
DECLARE @openPct int = $(OpenPercent);
DECLARE @t0 datetimeoffset = '2025-11-01T00:00:00+00:00';

DELETE FROM AuditEvents; DELETE FROM Decisions; DELETE FROM ReviewTasks; DELETE FROM ExtractedFields; DELETE FROM Submissions;

-- Numbers 1..N without a helper table.
WITH n AS (
    SELECT TOP (@subs) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS i
    FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c
)
INSERT INTO Submissions (Id, Pipeline, Status, InsuredName, TotalTiv, EffectiveDate, RecordJson, ReceivedAt, UpdatedAt)
SELECT CONCAT('PERF-', FORMAT(i, '000000')), 'final', 'NeedsReview', CONCAT('Insured ', i, ' LLC'),
       1000000 + (i % 97) * 250000, DATEADD(day, i % 180, '2026-12-01'), '{}',
       DATEADD(minute, i * 5, @t0), DATEADD(minute, i * 5, @t0)
FROM n;

-- @per flagged fields per submission; one review task each. About @openPct % stay open.
WITH n AS (
    SELECT TOP (@subs * @per) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS k
    FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c
), t AS (
    SELECT k, (k - 1) / @per + 1 AS i, (k - 1) % @per + 1 AS j FROM n
)
INSERT INTO ExtractedFields (SubmissionId, Path, ValueJson, Confidence, Status, IsCritical, Extractor,
                             CitationDocument, CitationPage, CitationLocator, CitationSnippet)
SELECT CONCAT('PERF-', FORMAT(i, '000000')), CONCAT('locations[', j, '].year_built'), CAST(1950 + k % 70 AS nvarchar(10)),
       0.5 + (k % 50) / 100.0,
       CASE k % 4 WHEN 0 THEN 'Conflict' WHEN 1 THEN 'Missing' WHEN 2 THEN 'LowConfidence' ELSE 'Invalid' END,
       CASE WHEN k % 3 = 0 THEN 1 ELSE 0 END, 'table_parser:local', 'SOV.pdf', 1 + j % 3, CONCAT('page 1 line ', j), 'row text'
FROM t;

WITH f AS (
    SELECT Id AS k, SubmissionId, Path, Status, IsCritical FROM ExtractedFields
)
INSERT INTO ReviewTasks (SubmissionId, FieldPath, FieldStatus, Reason, Priority, Status, CreatedAt, ResolvedAt, ResolvedBy, Resolution)
SELECT SubmissionId, Path, Status, 'synthetic perf task',
       -- same priority formula as IngestService.Priority
       (CASE WHEN IsCritical = 1 THEN 100 ELSE 0 END)
         + CASE Status WHEN 'Conflict' THEN 50 WHEN 'Invalid' THEN 50 WHEN 'Missing' THEN 40 ELSE 10 END,
       CASE WHEN k % 100 < @openPct THEN 'Open' ELSE 'Resolved' END,
       DATEADD(second, k * 30, @t0),
       CASE WHEN k % 100 < @openPct THEN NULL ELSE DATEADD(second, k * 30 + 3600, @t0) END,
       CASE WHEN k % 100 < @openPct THEN NULL ELSE 'uw1' END,
       CASE WHEN k % 100 < @openPct THEN NULL ELSE 'Confirmed' END
FROM f;

UPDATE STATISTICS ReviewTasks WITH FULLSCAN;
UPDATE STATISTICS ExtractedFields WITH FULLSCAN;
UPDATE STATISTICS Submissions WITH FULLSCAN;

SELECT (SELECT COUNT(*) FROM Submissions) AS submissions, (SELECT COUNT(*) FROM ExtractedFields) AS fields,
       (SELECT COUNT(*) FROM ReviewTasks) AS tasks, (SELECT COUNT(*) FROM ReviewTasks WHERE Status = 'Open') AS open_tasks;
