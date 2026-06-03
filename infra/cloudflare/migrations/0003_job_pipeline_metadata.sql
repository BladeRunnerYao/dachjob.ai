-- Pipeline import metadata and canonical job identity.

ALTER TABLE jobs ADD COLUMN job_key TEXT DEFAULT NULL;
ALTER TABLE jobs ADD COLUMN pipeline_added_at TEXT DEFAULT NULL;
ALTER TABLE jobs ADD COLUMN pipeline_source_sha TEXT DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_user_job_key ON jobs(user_id, job_key);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(user_id, company);
CREATE INDEX IF NOT EXISTS idx_jobs_pipeline_added_at ON jobs(user_id, pipeline_added_at);
