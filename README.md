# VAS2Font

VAS2Font turns handwriting created in [vas](https://github.com/gengyunmaster/vas) into a personal OpenType font. Generate a PDF writing template, write in vas, upload the exported notebook JSON, and preview or download your font in a browser.

The application requires no accounts. A private, high-entropy access code protects each project.

## Features

- CFF/OTF generation from pressure-sensitive vas vector strokes.
- Six built-in templates covering representative characters, Latin letters, digits, ASCII punctuation, GB2312 Han characters, and combined GB2312/ASCII coverage.
- Custom Unicode character set templates with generated A4 PDF writing guides.
- Multiple notebook uploads with priority-based glyph replacement for batch writing and corrections.
- Glyph coverage and provenance inspector with search, filters, previews, and correction-template creation.
- Asynchronous font generation with real stage and percentage progress.
- Browser font preview and OTF download from the same in-memory Blob.
- Portable project backup and import without exporting access codes.
- PostgreSQL JSONB storage, soft deletion, migrations, and automatic built-in template initialization.
- Responsive parchment, tea, ink, and cinnabar visual design.

Generated fonts and PDFs are not stored persistently. Font results are deleted from temporary storage after their one-time download response is consumed.

## Technology stack

- Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, asyncpg, Alembic
- PostgreSQL 19
- React 19, TypeScript, Vite, Biome
- FontTools, Skia PathOps, ReportLab
- Node.js and perfect-freehand for vas-compatible stroke outlines
- Docker and Docker Compose
- pytest, Playwright, and GitHub Actions

Python and Node dependencies are locked in `uv.lock` and the npm lockfiles.

## Quick start with Docker

Requirements: Git, Docker, and Docker Compose.

```bash
git clone https://github.com/gengyunmaster/vas2font.git
cd vas2font
docker compose up -d --build
```

Open http://localhost:8000.

The web container runs Alembic migrations automatically before starting the application. PostgreSQL data is stored in the `postgres-data-v19` Docker volume.

Useful commands:

```bash
docker compose ps
docker compose logs -f web
docker compose down
```

`docker compose down` stops containers but preserves the database volume.

## Local development

### Prerequisites

- Git
- Python 3.12
- uv 0.11.15
- Node.js 24 and npm
- Docker for the development PostgreSQL instance

Install the locked Python and Node dependencies:

```bash
git clone https://github.com/gengyunmaster/vas2font.git
cd vas2font
uv sync --locked
npm ci --prefix frontend
npm ci --prefix src/vas2font/node
```

Start a local PostgreSQL 19 instance on port 55432:

```bash
docker run -d \
  --name vas2font-dev-postgres \
  -e POSTGRES_USER=vas2font \
  -e POSTGRES_PASSWORD=vas2font \
  -e POSTGRES_DB=vas2font \
  -p 55432:5432 \
  postgres:19.0
```

The default `DATABASE_URL` matches this development container. Run migrations and start the API:

```bash
uv run alembic upgrade head
uv run uvicorn vas2font.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Build the frontend once so FastAPI can serve it:

```bash
npm run --prefix frontend build
```

For frontend hot reload, run Vite in another terminal:

```bash
npm run --prefix frontend dev
```

Open http://localhost:5173. Vite proxies `/api` to port 8000.

Stop the development database when finished:

```bash
docker stop vas2font-dev-postgres
```

Restart it later with `docker start vas2font-dev-postgres`.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://vas2font:vas2font@localhost:55432/vas2font` | Async PostgreSQL connection |
| `FRONTEND_DIST` | `frontend/dist` | Built frontend served by FastAPI |
| `MAX_UPLOAD_BYTES` | `134217728` | Maximum notebook upload size, 128 MiB |
| `OPEN_RATE_LIMIT` | `10` | Project open/import requests per minute per IP |
| `GENERATION_RATE_LIMIT` | `20` | Font generation requests per minute per IP |
| `WEB_PORT` | `8000` | Host port used by Docker Compose |
| `POSTGRES_PASSWORD` | `vas2font` | Compose database password; change it in production |

## Tests and quality checks

Run Python checks:

```bash
uv run ruff check src migrations tests
uv run ruff format --check src migrations tests
uv run pytest
```

Run frontend checks:

```bash
npm run --prefix frontend lint
npm run --prefix frontend build
```

Run browser regression tests against a running application on port 8000:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

To use another application URL:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:8001 npm run --prefix frontend test:e2e
```

The Playwright workflow covers project creation, real notebook upload, glyph inspection, correction templates, asynchronous OTF generation, backup download, and project import.

The GitHub Actions workflow in `.github/workflows/ci.yml` runs all quality gates and starts a real PostgreSQL-backed Docker environment for browser tests.

## Command-line font tools

Generate a PDF and its coordinate manifest:

```bash
uv run vas2font generate-template \
  --charset representative-100 \
  --version 1 \
  --output-dir build
```

Generate OTF and diagnostic TrueType fonts from an exported vas notebook:

```bash
uv run vas2font generate-font \
  --notebook samples/representative-100-v1/notebook.json \
  --charset representative-100 \
  --version 1 \
  --font-family "My Handwriting" \
  --font-version 1.0 \
  --output build/my-handwriting.otf \
  --ttf-output build/my-handwriting.ttf
```

## Build runtime Docker images

Build both the web image and pull the exact PostgreSQL runtime image:

```bash
docker compose build
docker compose pull db
```

The resulting runtime images are:

- `vas2font-web:latest`
- `postgres:19.0`

The web image already contains its Python, Node.js, font assets, frontend assets, and native library dependencies. Base build images do not need to be exported separately.

## Export images for offline installation

On a connected machine, from the repository root:

```bash
docker compose build
docker compose pull db
docker save vas2font-web:latest postgres:19.0 | gzip > vas2font-images.tar.gz
tar -czf vas2font-offline-bundle.tar.gz compose.yaml vas2font-images.tar.gz
```

Copy `vas2font-offline-bundle.tar.gz` to the offline machine. Use an image archive built for the same CPU architecture as that machine, such as `linux/amd64` or `linux/arm64`.

On the offline machine, with Docker and Docker Compose already installed:

```bash
tar -xzf vas2font-offline-bundle.tar.gz
gunzip -c vas2font-images.tar.gz | docker load
export POSTGRES_PASSWORD='replace-with-a-strong-password'
docker compose up -d --no-build
docker compose ps
```

Open `http://localhost:8000`, or set `WEB_PORT` before starting Compose to use another port.

The offline machine does not need access to PyPI, npm, GitHub, or Docker Hub.

## Production deployment

1. Use a machine with Docker, Docker Compose, and a PostgreSQL 19-compatible volume.
2. Set a strong `POSTGRES_PASSWORD` through the deployment environment or secret manager. Do not commit it.
3. Build and start the services:

   ```bash
   export POSTGRES_PASSWORD='replace-with-a-strong-password'
   export WEB_PORT=8000
   docker compose up -d --build
   ```

4. Confirm both services are healthy:

   ```bash
   docker compose ps
   docker compose logs web
   ```

5. Put Caddy, Nginx, or another TLS reverse proxy in front of the web port. Production access should use HTTPS.
6. Restrict access to the host and database network. The Compose database is not exposed on a host port by default.
7. Back up PostgreSQL regularly and store backups separately from the database volume.

Alembic migrations run automatically when the web container starts. The deployment uses PostgreSQL 19's `/var/lib/postgresql` volume layout.

Project access codes grant full project control. They are stored only as SHA-256 hashes and should never appear in URLs or logs.

## Database backup and restore

### Full PostgreSQL backup

Create a compressed SQL dump:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U vas2font -d vas2font \
  | gzip > "backups/vas2font-$(date +%Y%m%d-%H%M%S).sql.gz"
```

Test backups regularly and keep an off-host copy. Soft deletion is not a substitute for backups.

### Restore into a new empty database

Restore only into a newly initialized, empty database. Stop the web application first:

```bash
docker compose stop web
gunzip -c backups/vas2font-YYYYMMDD-HHMMSS.sql.gz \
  | docker compose exec -T db psql -U vas2font -d vas2font
docker compose up -d web
```

For a PostgreSQL major-version upgrade, dump the old database, initialize a separate new-major-version volume, restore the dump, verify application data and record counts, and retain the old volume until the upgrade is accepted. Do not point a new PostgreSQL major version directly at an older major version's data files.

### Portable project backup

Use **Overview → Download backup** to export one project's metadata, custom templates, original notebooks, and priority order. Use **Import project backup** on the home page to restore it as a new project with a new access code.

Portable backups exclude access codes. Full database dumps include all projects and internal audit records and should be protected accordingly.

## Data storage and deletion

- PostgreSQL is the only durable application data store.
- Notebook JSON is stored as JSONB.
- Projects, templates, uploads, and generation jobs use audit timestamps and soft deletion where applicable.
- Generated OTF bytes are never stored in PostgreSQL.
- Generated PDF files are not stored persistently.
- Deleting a project disables access but does not physically erase its records.

## Design documentation

The finalized architecture and API behavior are documented in [`docs/web-design.md`](docs/web-design.md).

## License

The project source code is available under the [MIT License](LICENSE).

Bundled Noto reference fonts are licensed under the SIL Open Font License. Their license files are included in `src/vas2font/assets/`.
