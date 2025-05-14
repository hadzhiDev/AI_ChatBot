FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Recommended to use a script to run multiple commands
# COPY entrypoint.sh .
# RUN chmod +x entrypoint.sh

# The compose file will override this when using volumes
CMD ["sh", "-c", "python3 manage.py runserver 0.0.0.0:8000 && python3 manage.py telegram"]