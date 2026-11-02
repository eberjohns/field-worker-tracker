-- Roles per docs/13-architecture.md section 9
DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'fw_migrator') THEN
        CREATE ROLE fw_migrator WITH LOGIN PASSWORD 'fw_migrator_secret' SUPERUSER;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'fw_app') THEN
        CREATE ROLE fw_app WITH LOGIN PASSWORD 'fw_secret';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'fw_readonly') THEN
        CREATE ROLE fw_readonly WITH LOGIN PASSWORD 'fw_readonly_secret';
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON DATABASE fw_db TO fw_migrator;
GRANT ALL PRIVILEGES ON SCHEMA public TO fw_migrator;
ALTER SCHEMA public OWNER TO fw_migrator;

GRANT CONNECT ON DATABASE fw_db TO fw_app;
GRANT USAGE ON SCHEMA public TO fw_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO fw_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fw_migrator IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO fw_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fw_migrator IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO fw_app;

GRANT CONNECT ON DATABASE fw_db TO fw_readonly;
GRANT USAGE ON SCHEMA public TO fw_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO fw_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE fw_migrator IN SCHEMA public GRANT SELECT ON TABLES TO fw_readonly;
