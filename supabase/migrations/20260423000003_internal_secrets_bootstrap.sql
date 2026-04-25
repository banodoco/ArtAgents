-- Operator seed command:
-- INSERT INTO internal.secrets (name, value)
-- VALUES ('service_role_key', '<SERVICE_ROLE_KEY>')
-- ON CONFLICT (name) DO UPDATE
-- SET value = EXCLUDED.value,
--     updated_at = NOW();

CREATE SCHEMA IF NOT EXISTS internal AUTHORIZATION postgres;

CREATE TABLE IF NOT EXISTS internal.secrets (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER SCHEMA internal OWNER TO postgres;
ALTER TABLE internal.secrets OWNER TO postgres;
ALTER TABLE internal.secrets ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON SCHEMA internal FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON internal.secrets FROM PUBLIC, anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION internal.get_service_role_key()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
    SELECT value
    FROM internal.secrets
    WHERE name = 'service_role_key'
    LIMIT 1;
$$;

ALTER FUNCTION internal.get_service_role_key() OWNER TO postgres;
REVOKE ALL ON FUNCTION internal.get_service_role_key() FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION internal.get_service_role_key() TO postgres;
