-- Track when a job was first marked as applied.

ALTER TABLE jobs ADD COLUMN application_applied_at TEXT DEFAULT NULL;

UPDATE jobs
SET application_applied_at = COALESCE(updated_at, created_at)
WHERE application_status = 'applied'
  AND application_applied_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_application_applied_at ON jobs(user_id, application_applied_at);
