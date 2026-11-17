-- Apply once with psql -v ON_ERROR_STOP=1 against postgres_visitor_vehicle.
BEGIN;
CREATE TABLE IF NOT EXISTS enrollment_data_jobs (
    id uuid PRIMARY KEY,
    operation text NOT NULL CHECK (operation IN ('export', 'validate', 'import', 'reset')),
    requested_by bigint NOT NULL REFERENCES users(id),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','completed','failed','cancelled','recovery_required')),
    step text NOT NULL DEFAULT 'pending',
    checkpoint text NOT NULL DEFAULT 'pending',
    input_id uuid,
    preview_id uuid,
    import_plan jsonb,
    result jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_summary text,
    attempts integer NOT NULL DEFAULT 0,
    heartbeat_at timestamptz,
    dispatched_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
ALTER TABLE enrollment_data_jobs ADD COLUMN IF NOT EXISTS preview_id uuid;
ALTER TABLE enrollment_data_jobs ADD COLUMN IF NOT EXISTS import_plan jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS enrollment_data_one_active
ON enrollment_data_jobs ((true)) WHERE status IN ('queued','running','recovery_required');
CREATE INDEX IF NOT EXISTS enrollment_data_job_history ON enrollment_data_jobs(created_at DESC);

CREATE TABLE IF NOT EXISTS enrollment_data_steps (
    job_id uuid NOT NULL REFERENCES enrollment_data_jobs(id),
    sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    step text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);

-- Writers that bypass HTTP also fail closed while maintenance is active.
CREATE OR REPLACE FUNCTION enrollment_data_write_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE active_id text;
BEGIN
    SELECT id::text INTO active_id FROM enrollment_data_jobs
    WHERE status IN ('running','recovery_required') OR (status='queued' AND checkpoint <> 'pending') LIMIT 1;
    IF active_id IS NOT NULL AND current_setting('enrollment_data.job_id', true) IS DISTINCT FROM active_id THEN
        RAISE EXCEPTION 'Enrollment maintenance active; retry after completion or recovery';
    END IF;
    IF current_setting('enrollment_data.job_id', true) IS DISTINCT FROM active_id OR active_id IS NULL THEN
        IF NOT pg_try_advisory_xact_lock_shared(74109321) THEN
            RAISE EXCEPTION 'Enrollment maintenance active; retry later';
        END IF;
    END IF;
    RETURN NULL;
END $$;
DO $$ DECLARE t text; BEGIN
    FOREACH t IN ARRAY ARRAY['persons','vehicles','trips','passes'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS enrollment_data_guard ON %I', t);
        EXECUTE format('CREATE TRIGGER enrollment_data_guard BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE ON %I FOR EACH STATEMENT EXECUTE FUNCTION enrollment_data_write_guard()', t);
    END LOOP;
END $$;
COMMIT;
