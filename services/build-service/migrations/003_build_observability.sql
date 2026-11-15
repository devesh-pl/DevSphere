CREATE OR REPLACE VIEW build_observability AS
SELECT
    created_at,
    updated_at,
    status,
    attempt_count,
    CASE
        WHEN status IN ('completed', 'failed')
        THEN GREATEST(
            EXTRACT(EPOCH FROM (updated_at - created_at)),
            0
        )::double precision
        ELSE NULL
    END AS turnaround_seconds
FROM build_jobs;
