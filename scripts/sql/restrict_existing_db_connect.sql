-- Run as postgres superuser on the existing PostgreSQL instance.
-- Does NOT drop database, schema, table or data.
REVOKE CONNECT, TEMPORARY ON DATABASE auth_db FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE room_db FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE tenant_db FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE metering_db FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE billing_db FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE notification_db FROM PUBLIC;

SELECT datname AS db_name,
       has_database_privilege('room_app', datname, 'CONNECT') AS room_app_can_connect,
       has_database_privilege('tenant_app', datname, 'CONNECT') AS tenant_app_can_connect
FROM pg_database WHERE datname IN ('auth_db','room_db','tenant_db','metering_db','billing_db','notification_db')
ORDER BY datname;
