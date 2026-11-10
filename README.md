# Rental Management - Microservices

Five FastAPI business services (Room, Tenant, Metering, Billing, Notification),
FastAPI Auth, Nginx API Gateway, PostgreSQL (six logical DBs), RabbitMQ + MQTT,
Python IoT simulator, React frontend (not scaffolded here).

This scaffold creates the file layout, minimal FastAPI health endpoints,
Dockerfiles, and Alembic templates. It is NOT a running integrated system yet.
Fill contracts, infra configuration, business ORM models, and compose files next.
Run Alembic revision generation after ORM models are written.

Do not expose service/internal API ports, PostgreSQL, or RabbitMQ publicly.