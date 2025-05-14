#!/bin/bash

# Wait for PostgreSQL using pg_isready
echo "Waiting for PostgreSQL..."
while ! python -c "import psycopg2; psycopg2.connect(dbname='${POSTGRES_DB}', user='${POSTGRES_USER}', password='${POSTGRES_PASSWORD}', host='postgres')" 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL started"

# Rest of your script remains the same
python manage.py migrate
python manage.py runserver 0.0.0.0:8000 &
python manage.py telegram
wait