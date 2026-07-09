# Django Google Drive Clone

A full-featured Google Drive clone built with Django, supporting real-time file synchronization, file sharing, notifications, and background task processing.

---

## Features

- 📁 **File & Folder Management** — Create, upload, rename, move, and organize files/folders in a nested hierarchy.
- 🗑️ **Soft Delete & Trash** — Deleted items move to Trash and can be restored or permanently removed.
- ⚡ **Real-Time Synchronization** — Two-tab synchronization using Django Channels (WebSockets).
- 🔗 **Sharing & Permissions** — Share files/folders with other users with configurable permissions.
- 🔔 **Notifications** — Persistent in-app notifications.
- 📧 **Email Notifications** — HTML email alerts sent asynchronously using Celery.
- ⏰ **Scheduled Cleanup** — Celery Beat automatically deletes expired trashed items.
- ✅ **Automated Testing** — Tests written with pytest and pytest-django.

---

# Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5 |
| Database | PostgreSQL |
| Real-Time | Django Channels |
| Message Broker | Redis |
| Background Tasks | Celery |
| Task Scheduler | Celery Beat |
| Static Files | WhiteNoise |
| Frontend | Bootstrap + Vanilla JavaScript |
| Testing | pytest, pytest-django |
| Containerization | Docker & Docker Compose |

---

# Running with Docker (Recommended)

## Prerequisites

- Docker Desktop
- Docker Compose

## Clone the repository

```bash
git clone https://github.com/awais9642/django-google-drive-clone.git
cd django-google-drive-clone
```

## Create the Docker environment file

Copy the example environment file:

### Windows (PowerShell)

```powershell
Copy-Item .env.example .env.docker
```

### macOS / Linux

```bash
cp .env.example .env.docker
```

Open `.env.docker` and update the values if needed (for example, your email credentials and Django `SECRET_KEY`).

## Build and start the containers

```bash
docker compose up --build
```

The application will be available at:

```
http://localhost:8000
```

Docker automatically starts:

- Django (Daphne)
- PostgreSQL
- Redis
- Celery Worker
- Celery Beat

No manual installation of PostgreSQL, Redis, or Celery is required.

## Stopping the application

```bash
docker compose down
```

## Rebuilding after dependency changes

If you modify `requirements.txt`, `Dockerfile`, or `docker-compose.yml`, rebuild the images:

```bash
docker compose up --build
```

# Running Without Docker

## Prerequisites

- Python 3.10+
- PostgreSQL
- Redis (or Memurai on Windows)

### Create a virtual environment

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

macOS/Linux

```bash
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Create a `.env` file

```env
SECRET_KEY=your-secret-key

DEBUG=True

DB_NAME=drive_clone_db
DB_USER=drive_clone_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://127.0.0.1:6379/1

EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com
```

### Apply migrations

```bash
python manage.py migrate
```

### Create superuser

```bash
python manage.py createsuperuser
```

---

# Run Services

Open four terminals.

### Terminal 1

Redis (or Memurai)

### Terminal 2

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

### Terminal 3

```bash
celery -A config worker -l info -P solo
```

### Terminal 4

```bash
celery -A config beat -l info
```

Visit:

```
http://localhost:8000
```

---

# Running Tests

```bash
pytest
```

---

# Project Structure

```
django-google-drive-clone/
│
├── accounts/
├── drive/
├── notifications/
├── sharing/
├── config/
│   ├── settings.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── celery.py
│
├── templates/
├── static/
├── media/
│
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── .dockerignore
├── requirements.txt
├── .env.example
├── manage.py
└── README.md
```

---

# Environment Variables

The repository does **not** include your actual environment files.

Create one of the following:

- `.env` → Local development
- `.env.docker` → Docker environment

Use `.env.example` as a reference.

---

# License

This project was developed as part of an internal technical assessment.
