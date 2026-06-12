-- Track when jobs first enter each saved/application status.

ALTER TABLE jobs ADD COLUMN saved_at TEXT DEFAULT NULL;
ALTER TABLE jobs ADD COLUMN application_interview_at TEXT DEFAULT NULL;
ALTER TABLE jobs ADD COLUMN application_rejected_at TEXT DEFAULT NULL;
ALTER TABLE jobs ADD COLUMN application_offer_at TEXT DEFAULT NULL;

UPDATE jobs
SET saved_at = COALESCE(updated_at, created_at)
WHERE saved = 1
  AND saved_at IS NULL;

UPDATE jobs
SET application_interview_at = COALESCE(updated_at, created_at)
WHERE application_status = 'interview'
  AND application_interview_at IS NULL;

UPDATE jobs
SET application_rejected_at = COALESCE(updated_at, created_at)
WHERE application_status = 'rejected'
  AND application_rejected_at IS NULL;

UPDATE jobs
SET application_offer_at = COALESCE(updated_at, created_at)
WHERE application_status = 'offer'
  AND application_offer_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_jobs_saved_at ON jobs(user_id, saved_at);
CREATE INDEX IF NOT EXISTS idx_jobs_application_interview_at ON jobs(user_id, application_interview_at);
CREATE INDEX IF NOT EXISTS idx_jobs_application_rejected_at ON jobs(user_id, application_rejected_at);
CREATE INDEX IF NOT EXISTS idx_jobs_application_offer_at ON jobs(user_id, application_offer_at);
