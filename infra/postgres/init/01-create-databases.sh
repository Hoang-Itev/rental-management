#!/bin/sh
set -eu

# Runs ONLY when postgres_data volume is initialized for the first time.
# Create separate ownership and login role for each logical database.
create_service_db() {
  db_name="$1"
  role_name="$2"
  role_pass="$3"
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
    -v app_db="$db_name" -v app_role="$role_name" -v app_pass="$role_pass" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_role', :'app_pass')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_role') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'app_db', :'app_role')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'app_db') \gexec
SQL
}

create_service_db auth_db auth_app "$AUTH_DB_PASSWORD"
create_service_db room_db room_app "$ROOM_DB_PASSWORD"
create_service_db tenant_db tenant_app "$TENANT_DB_PASSWORD"
create_service_db metering_db metering_app "$METERING_DB_PASSWORD"
create_service_db billing_db billing_app "$BILLING_DB_PASSWORD"
create_service_db notification_db notification_app "$NOTIFICATION_DB_PASSWORD"

echo 'Created six service-owned databases.'

# Default PUBLIC CONNECT allows cross-service DB login, even without table access.
# Restrict both CONNECT and TEMPORARY for fresh clusters.
restrict_service_db() {
  db_name="$1"
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
    -v app_db="$db_name" <<'SQL'
SELECT format('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', :'app_db') \gexec
SQL
}
for db in auth_db room_db tenant_db metering_db billing_db notification_db; do
  restrict_service_db "$db"
done
