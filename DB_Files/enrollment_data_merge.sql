-- Apply for installations that already have the initial worker migration.
-- Finish all legacy import/recovery jobs using the old code before upgrading.
BEGIN;
ALTER TABLE enrollment_data_jobs ADD COLUMN IF NOT EXISTS preview_id uuid;
ALTER TABLE enrollment_data_jobs ADD COLUMN IF NOT EXISTS import_plan jsonb;
COMMIT;
