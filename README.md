# TaskFlow – Task Management System

Application layer of the DevOps Bootcamp final project.

Repository, team, local-development, and infrastructure guidance is in [docs/](docs/), including the [shared Forogh server record](docs/infrastructure/shared-forogh-server.md) and [CI/CD pipeline guide](docs/ci-cd.md).

For Ubuntu setup and the verified local commands, see [Local development](docs/local-development.md).

## Infrastructure automation

The shared GitLab Runner Ansible role, inventory guidance, and run commands are documented in [ansible/README.md](ansible/README.md).

For Argo CD installation, Nexus registry access, and GitOps bootstrap, see the [Argo CD setup manual](docs/ansible/argocd-setup.md).

For SonarQube installation, GitLab CI static analysis, and the Quality Gate,
see the [SonarQube setup manual](docs/ansible/sonarqube-setup.md).

| Component | Technology | Location |
|-----------|------------|----------|
| Backend   | Python 3.11+ / FastAPI / SQLAlchemy | `backend/` |
| Database  | PostgreSQL | – |
| Cache     | Redis (optional at runtime, degrades gracefully) | – |
| Frontend  | React 18 + Vite, plain CSS | `frontend/` |

```
Browser ──► Frontend (static files, e.g. Nginx) ──/api/*──► Backend (FastAPI :8000) ──► PostgreSQL
                                                                              └──► Redis (cache)
```

The frontend always calls the backend through the relative path **`/api`**.
The backend serves every route both with and without the `/api` prefix
(`/tasks` and `/api/tasks`, `/health` and `/api/health`), so the reverse proxy
may either strip the prefix or forward it unchanged.

---

## Backend

### Configuration (environment variables)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | **yes** | – | e.g. `postgresql://user:password@postgres:5432/tasks` |
| `REDIS_HOST` | no | – (cache disabled) | Redis hostname, e.g. `redis` |
| `REDIS_PORT` | no | `6379` | |
| `REDIS_PASSWORD` | no | – | |
| `REDIS_DB` | no | `0` | |
| `CACHE_TTL_SECONDS` | no | `60` | TTL of cached list/stats responses |
| `DB_CONNECT_RETRIES` | no | `10` | Startup attempts while PostgreSQL is not ready |
| `DB_CONNECT_RETRY_DELAY` | no | `3` | Seconds between attempts |
| `LOG_LEVEL` | no | `INFO` | |
| `APP_VERSION` | no | `1.0.0` | Shown in `/health` (handy to verify rolling updates) |
| `CORS_ORIGINS` | no | – | Comma-separated origins; only needed if the frontend is served from another origin without a proxy |

Secrets (`DATABASE_URL`, `REDIS_PASSWORD`) are never logged or returned by the API.

### Run locally

The backend uses relative imports. Run it from the repository root as the `backend` package:

```bash
python -m pip install -r backend/requirements.txt
export DATABASE_URL="postgresql://taskflow:taskflow_dev_password@localhost:5432/tasks"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Tables are created automatically on startup. Databases created by the previous
version of the app are upgraded in place (missing columns are added).

Interactive API docs: `http://localhost:8000/docs`

### Tests and lint

Tests use a temporary SQLite database and no Redis, so no infrastructure is needed (suitable for the CI test stage):

```bash
source .venv/bin/activate
python -m pip install -r backend/requirements.txt ruff pytest httpx
ruff check backend
python -m pytest backend/tests
```

Ruff is a project tool: install it in `.venv`, rather than system-wide with
Snap. For Ruff errors marked as fixable, use `ruff check backend --fix`, inspect
the diff, and rerun lint and tests before committing. CI reports these errors;
it does not modify source files for you.

### API

| Method | Path | Description | Success |
|--------|------|-------------|---------|
| GET | `/health` | Status of the API + PostgreSQL + Redis. Always `200` while the process is alive | 200 |
| GET | `/health/live` | Liveness probe (no dependency checks) | 200 |
| GET | `/health/ready` | Readiness probe – `503` when PostgreSQL is unreachable | 200 / 503 |
| GET | `/tasks/` | List tasks (see query parameters). Total count in `X-Total-Count` header | 200 |
| POST | `/tasks/` | Create a task | 201 |
| GET | `/tasks/stats` | Dashboard statistics | 200 |
| GET | `/tasks/{id}` | Get one task | 200 / 404 |
| PATCH | `/tasks/{id}` | Partially update a task | 200 / 404 / 422 |
| DELETE | `/tasks/{id}` | Delete a task | 204 / 404 |

`GET /tasks/` query parameters (all optional – without parameters it returns all tasks, as before):
`search`, `status` (`todo`/`in_progress`/`done`), `priority` (`low`/`medium`/`high`), `overdue` (`true`/`false`),
`sort` (`created_at`, `updated_at`, `due_date`, `priority`, `status`, `title`), `order` (`asc`/`desc`), `limit` (1–100), `offset`.

Task object:

```json
{
  "id": 1,
  "title": "Configure readiness probe",
  "description": "Use /health/ready",
  "status": "in_progress",
  "priority": "high",
  "due_date": "2026-09-30",
  "created_at": "2026-09-16T10:00:00Z",
  "updated_at": "2026-09-16T11:00:00Z",
  "owner_id": null,
  "is_overdue": false
}
```

Errors always have a `detail` message; validation errors (`422`) also include `errors: [{field, message}]`.
Database failures return a generic `503`/`500` message without internal details.

#### Kubernetes probe suggestion

```yaml
livenessProbe:
  httpGet: { path: /health/live, port: 8000 }   # or /health
readinessProbe:
  httpGet: { path: /health/ready, port: 8000 }
```

---

## Frontend

```bash
cd frontend
npm ci            # or npm install
npm run dev       # http://localhost:3000, proxies /api to BACKEND_URL (default http://localhost:8000)
npm run lint
npm test
npm run build     # static files in dist/
```

| Variable | When | Default | Description |
|----------|------|---------|-------------|
| `BACKEND_URL` | `npm run dev` only | `http://localhost:8000` | Target of the dev-server `/api` proxy |
| `VITE_API_BASE_URL` | build time | `/api` | Base path of the API as seen by the browser. Keep the default when a reverse proxy is used |

Serving the production build (e.g. with Nginx) needs two things:

1. **SPA fallback** – client-side routes (`/tasks`, `/status`) must return `index.html`
   (`try_files $uri $uri/ /index.html;`).
2. **API proxy** – forward `/api/` to the backend service (e.g. `proxy_pass http://backend:8000;`).





---

## Project

Developed for **Hamrah Academy DevOps Bootcamp**.
