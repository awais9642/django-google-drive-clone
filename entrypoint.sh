#!/bin/sh

echo "Waiting for PostgreSQL..."

while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

echo "PostgreSQL started."

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Daphne..."

exec daphne -b 0.0.0.0 -p 8000 config.asgi:application