# Django Booking Sync

A Django + Django REST Framework project that syncs appointment data from [Easy!Appointments](https://easyappointments.org/) and exposes it via a clean REST API.

---

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

---

## Installation

### 🪟 Windows

```powershell
# 1. Clone the repo
git clone https://github.com/yasirnabil534/django-booking-example.git
cd django-booking-example

# 2. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
Copy-Item .env.example .env   # then edit .env with your values

# 5. Start Easy!Appointments
docker compose up -d

# 6. Run migrations
python manage.py migrate

# 7. (Optional) Seed test data
python scripts/seed_data.py

# 8. Start dev server
python manage.py runserver
```

> ⚠️ If `.\venv\Scripts\Activate.ps1` is blocked, run:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

---

### 🍎 macOS

```bash
# 1. Clone the repo
git clone https://github.com/yasirnabil534/django-booking-example.git
cd django-booking-example

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env   # then edit .env with your values

# 5. Start Easy!Appointments
docker compose up -d

# 6. Run migrations
python manage.py migrate

# 7. (Optional) Seed test data
python scripts/seed_data.py

# 8. Start dev server
python manage.py runserver
```

> 💡 If `python3` is not found, install it via [Homebrew](https://brew.sh/):
> `brew install python`

---

### 🐧 Linux (Ubuntu/Debian)

```bash
# 1. Install Python if not already installed
sudo apt update && sudo apt install -y python3 python3-venv python3-pip

# 2. Clone the repo
git clone https://github.com/yasirnabil534/django-booking-example.git
cd django-booking-example

# 3. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create .env file
cp .env.example .env   # then edit .env with your values

# 6. Start Easy!Appointments
docker compose up -d

# 7. Run migrations
python manage.py migrate

# 8. (Optional) Seed test data
python scripts/seed_data.py

# 9. Start dev server
python manage.py runserver
```

> 💡 Install Docker on Linux: [docs.docker.com/engine/install/ubuntu](https://docs.docker.com/engine/install/ubuntu/)

---

## Running Background Services

The sync pipeline uses **Celery** (task queue) + **Redis** (broker). Both are included in `docker-compose.yml` — no manual setup needed.

### Option A — Docker (recommended)

Spin up **everything** — Easy!Appointments, MySQL, Redis, Django, Celery worker, and Celery Beat — with a single command:

```bash
docker compose up -d
```

| Container | Role |
|---|---|
| `django-booking-example-redis-1` | Message broker |
| `django-booking-example-web-1` | Django API at `http://localhost:8000` |
| `django-booking-example-celery_worker-1` | Executes sync tasks |
| `django-booking-example-celery_beat-1` | Schedules sync every 6 hours |

> On first run, Docker builds the app image automatically from the `Dockerfile`.
> Subsequent runs reuse the cached image (fast).

To rebuild after adding new dependencies:
```bash
docker compose up -d --build
```

### Option B — Run locally (for development / debugging)

If you prefer to run Django and Celery outside Docker (e.g. for faster iteration), start only the infrastructure via Docker and run the processes manually:

```bash
# 1. Start Redis + Easy!Appointments + MySQL only
docker compose up -d redis easyappointments mysql

# 2. Django dev server (separate terminal)
python manage.py runserver

# 3. Celery worker (separate terminal)
celery -A config worker --loglevel=info

# 4. Celery Beat (separate terminal)
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Manual sync trigger

Trigger a sync on demand via the API:

```bash
# Trigger full sync for booking system ID=1
curl -X POST http://127.0.0.1:8000/api/booking-systems/1/sync/
# → {"data": {"task_id": "..."}, "errors": [], "meta": null}

# Check sync status
curl http://127.0.0.1:8000/api/booking-systems/1/sync/status/
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/booking-systems/connect/` | Register a new booking system |
| `GET` | `/api/booking-systems/{id}/status/` | Connection status + record counts |
| `GET` | `/api/booking-systems/{id}/providers/` | List providers (paginated, `?search=`) |
| `GET` | `/api/booking-systems/{id}/customers/` | List customers (paginated, `?search=`) |
| `GET` | `/api/booking-systems/{id}/services/` | List services (paginated) |
| `GET` | `/api/booking-systems/{id}/appointments/` | List appointments (paginated, `?start_date=`, `?end_date=`) |
| `POST` | `/api/booking-systems/{id}/sync/` | Trigger a full background sync, returns `task_id` |
| `GET` | `/api/booking-systems/{id}/sync/status/` | Sync status, `last_synced_at`, last error |

### Request & Response Format

**Connect a booking system:**
```json
POST /api/booking-systems/connect/
{
  "name": "My Salon",
  "base_url": "http://localhost:8888",
  "username": "admin",
  "password": "admin123"
}
```

**All responses use the standardized envelope:**
```json
{
  "data": [...],
  "errors": [],
  "meta": { "page": 1, "total_pages": 5, "total_count": 100 }
}
```

**Error responses:**
```json
{
  "data": null,
  "errors": [{ "message": "No BookingSystem matches the given query." }],
  "meta": null
}
```

### Interactive API Docs

| URL | Description |
|---|---|
| `http://127.0.0.1:8000/api/docs/` | Swagger UI |
| `http://127.0.0.1:8000/api/docs/redoc/` | ReDoc |
| `http://127.0.0.1:8000/api/schema/` | Raw OpenAPI 3.0 schema |

---

## Project Structure

```
django-booking-example/
├── manage.py                    # Django CLI entry point
├── docker-compose.yml           # Easy!Appointments + MySQL
├── requirements.txt             # Python dependencies
├── .env                         # Local environment variables (gitignored)
├── scripts/
│   └── seed_data.py             # Seed Easy!Appointments with test data
├── config/                      # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── apps/
    ├── core/                    # Shared utilities
    │   ├── pagination.py        # EnvelopePagination
    │   └── renderers.py         # EnvelopeRenderer
    └── booking_systems/         # Main feature app
        ├── models.py            # BookingSystem, Provider, Customer, Service, Appointment
        ├── serializers.py
        ├── views.py
        └── urls.py
```

---

## Design Decisions

**Flat Django project layout**
Django is scaffolded at the repo root (`django-admin startproject config .`) avoiding unnecessary nesting. The `config/` package holds settings/urls, `apps/` holds feature code.

**Global envelope renderer**
A custom DRF renderer (`apps/core/renderers.py`) wraps every response in `{data, errors, meta}` automatically. No per-view boilerplate — views return normal DRF `Response` objects.

**`external_id` uniqueness per booking system**
Each synced model enforces `unique_together = [("booking_system", "external_id")]` so the sync pipeline can run repeatedly without creating duplicates (idempotent upserts).

**Credentials stored as JSONField**
`BookingSystem.credentials` stores `{"username": "...", "password": "..."}` in a JSON column. The field is write-only in the serializer — never returned in API responses.

**SQLite for local development**
Zero-friction local setup with no external DB. Swap `DATABASES` in `settings.py` to PostgreSQL for production.

---

## Stopping Docker

```bash
docker compose down        # stop containers, keep data volume
docker compose down -v     # stop containers AND wipe data volume (fresh start)
```