# ZeroPain Docker Deployment Plan

This plan describes the containerized deployment for the ZeroPain stack on a Docker-based VPS with Caddy reverse proxy and security controls.

## Architecture Overview
- **Caddy**: TLS termination, rate limiting, security headers, reverse proxy to web and API.
- **Web (React + Nginx)**: Serves the SPA built with Vite.
- **API (FastAPI + Gunicorn/Uvicorn workers)**: Authentication, docking/ADMET job orchestration, health endpoints.
- **PostgreSQL**: Persistent application database; initialized via `docker/init-db.sql`.
- **Redis**: Session cache and token revocation list.

## Network Topology
- All services share the default Docker bridge network `zeropain_net` defined in `docker-compose.yml`.
- Caddy listens on ports 80/443 and proxies to:
  - `zeropain-web:80` for the SPA.
  - `zeropain-api:8000` for HTTP API.
  - `zeropain-api:8000` for WebSockets (`/ws/*`).

## Security Controls
- HTTPS termination with automatic certificate management (ACME). For local development, set `DOMAIN=localhost` to use HTTP.
- Strict security headers (HSTS, CSP, X-Frame-Options, Referrer-Policy) applied at Caddy.
- Rate limiting zones for API and docking workloads to protect from abuse.
- JWT-based authentication with refresh tokens; tokens signed using `SECRET_KEY` and `ALGORITHM` defined in environment.
- Recommended mTLS between Caddy and backend when running in untrusted networks; Caddyfile includes placeholders for certificate paths.

## Build Artifacts
- **API image** (`docker/Dockerfile.api`): multi-stage build with Python 3.11 slim base. Runs Gunicorn with Uvicorn workers.
- **Web image** (`docker/Dockerfile.web`): multi-stage Node 20 build to compile Vite React app, served by Nginx with hardened config (`docker/nginx.conf`).

## Configuration
- `.env.example` lists all required variables. Copy to `.env` and fill values for production.
- `docker/init-db.sql` initializes the database schema for users and job metadata.
- `docker-compose.yml` wires secrets, volumes, and health checks.

## Deployment Steps
1. Copy `.env.example` to `.env` and update values (DOMAIN, SECRET_KEY, database credentials).
2. Build and start the stack:
   ```bash
   docker compose up --build -d
   ```
3. Access the web UI via `https://<DOMAIN>` (or `http://localhost` for local testing).
4. Test API health: `curl -H "Authorization: Bearer <token>" https://<DOMAIN>/api/health`.

## Operations
- **Database backups**: use `docker exec postgres pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > backup.sql`.
- **Logs**: `docker compose logs -f caddy zeropain-api zeropain-web`.
- **Scaling**: adjust API worker count via `GUNICORN_WORKERS` and `GUNICORN_TIMEOUT` env vars; scale containers with `docker compose up --scale zeropain-api=2`.

## Contingency
- If TLS issuance fails, set `DOMAIN=localhost` and comment out the `tls` block in `Caddyfile` for HTTP-only testing.
- If GPU/NPU passthrough is unavailable, set `INTEL_DEVICE=CPU` to force CPU execution.
