# Django Drive Clone

A full-featured Google Drive clone built with Django, supporting real-time file sync, sharing, and background task processing.

## Features

- **File & Folder Management** — Create, upload, rename, move, and organize files/folders in a nested hierarchy
- **Soft Delete & Trash** — Deleted items go to trash and can be restored or permanently removed
- **Real-Time Sync** — Two-tab synchronization via WebSockets (Django Channels), so changes reflect instantly across open sessions
- **Sharing & Permissions** — Share files/folders with other users with configurable permission levels
- **Notifications** — Persistent in-app notifications for shares, updates, and system events
- **Email Notifications** — HTML email alerts sent asynchronously via Celery + Gmail SMTP
- **Scheduled Cleanup** — Celery Beat automatically purges trashed items after a set period
- **Automated Testing** — Test suite built with pytest-django covering core functionality

## Tech Stack

| Component | Technology |
|---|---|
| Backend Framework | Django |
| Database | PostgreSQL |
| Real-Time Layer | Django Channels + Redis (Memurai on Windows) |
| Task Queue | Celery + Celery Beat |
| Email | Gmail SMTP |
| Frontend | Bootstrap, Vanilla JavaScript |
| Testing | pytest, pytest-django |

## Prerequisites

- Python 3.10+
- PostgreSQL
- Redis (or [Memurai](https://www.memurai.com/) if on Windows)
- A Gmail account with an App Password for SMTP

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/awais9642/django-google-drive-clone.git
   cd django-google-drive-clone
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**

   Create a `.env` file in the project root:
   ```
   SECRET_KEY=your-secret-key
   DEBUG=True
   DATABASE_URL=postgres://user:password@localhost:5432/dbname
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-gmail-app-password
   REDIS_URL=redis://localhost:6379
   ```

5. **Run database migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

## Running the Project Locally

This project requires multiple processes running simultaneously — open a separate terminal for each:

**Terminal 1 — Redis/Memurai**
```bash
memurai
```

**Terminal 2 — Django (Daphne/ASGI server)**
```bash
daphne -b 0.0.0.0 -p 8000 your_project.asgi:application
```

**Terminal 3 — Celery Worker**
```bash
celery -A your_project worker -l info -P solo
```

**Terminal 4 — Celery Beat**
```bash
celery -A your_project beat -l info
```

Then visit `http://localhost:8000` in your browser.

## Running Tests

```bash
pytest
```

## Project Structure

```
django-google-drive-clone/
├── DRIVE_CLONE/          # Project settings, ASGI/WSGI config
├── drive_app/              # Core app: models, views, consumers
│   ├── models.py
│   ├── views.py
│   ├── consumers.py        # WebSocket consumers
│   ├── tasks.py            # Celery tasks
│   └── tests/
├── templates/
├── static/
├── requirements.txt
├── .env                    # Not committed — see .gitignore
└── manage.py
```

## Deployment

This project is configured for deployment on [Render](https://render.com/). Key considerations for production:

- Set `DEBUG=False`
- Configure `ALLOWED_HOSTS`
- Use a managed PostgreSQL and Redis instance
- Serve static files via WhiteNoise or a CDN
- Set all secrets via environment variables, never hardcoded

## License

This project was developed as part of an internal test/assignment task.
