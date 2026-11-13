-- Explicit deployment migration. Constructors never run production DDL.
CREATE TABLE IF NOT EXISTS public.l1lab_schema_migrations (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT statement_timestamp()
);

CREATE TABLE IF NOT EXISTS public.l1lab_runs (
    namespace text NOT NULL,
    run_id text NOT NULL,
    state jsonb NOT NULL,
    revision bigint NOT NULL DEFAULT 1,
    updated_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (namespace, run_id),
    CHECK (jsonb_typeof(state) = 'object'),
    CHECK (coalesce(state ->> 'run_id', '') = run_id),
    CHECK (revision > 0)
);

-- Independent receipt transactions are essential: a committed effect can be
-- reconciled even when the next journal write fails or its request crashes.
CREATE TABLE IF NOT EXISTS public.l1lab_sim_receipts (
    namespace text NOT NULL,
    idempotency_key text NOT NULL,
    fingerprint text NOT NULL,
    receipt jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    PRIMARY KEY (namespace, idempotency_key),
    CHECK (idempotency_key LIKE 'sim-key:%'),
    CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
    CHECK (jsonb_typeof(receipt) = 'object'),
    CHECK (coalesce(receipt ->> 'idempotency_key', '') = idempotency_key),
    CHECK (coalesce(receipt ->> 'payload_hash', '') = fingerprint),
    CHECK (coalesce(receipt ->> 'receipt_id', '') LIKE 'sim:%'),
    CHECK (coalesce(receipt ->> 'status', '') IN ('PENDING', 'VERIFIED')),
    CHECK (coalesce(receipt ->> 'gate', '') IN ('application','outreach','storage','commit','delivery'))
);

CREATE TABLE IF NOT EXISTS public.l1lab_action_budgets (
    namespace text NOT NULL,
    subject_hash text NOT NULL,
    action text NOT NULL,
    window_seconds integer NOT NULL,
    bucket_epoch bigint NOT NULL,
    used integer NOT NULL,
    PRIMARY KEY (namespace, subject_hash, action, window_seconds, bucket_epoch),
    CHECK (window_seconds BETWEEN 1 AND 3600),
    CHECK (used BETWEEN 1 AND 10000)
);
CREATE INDEX IF NOT EXISTS l1lab_budget_expiry
    ON public.l1lab_action_budgets (bucket_epoch);

INSERT INTO public.l1lab_schema_migrations(version) VALUES (1)
ON CONFLICT (version) DO NOTHING;
