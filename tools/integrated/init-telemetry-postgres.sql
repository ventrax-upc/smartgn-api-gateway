\getenv password DB_TELEMETRY
CREATE ROLE smartgn_telemetry LOGIN PASSWORD :'password';
REVOKE CONNECT ON DATABASE smartgn_telemetry FROM PUBLIC;
GRANT CONNECT ON DATABASE smartgn_telemetry TO smartgn_telemetry;
GRANT USAGE, CREATE ON SCHEMA public TO smartgn_telemetry;
