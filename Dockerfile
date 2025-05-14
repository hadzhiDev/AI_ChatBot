FROM python:3.11-alpine3.16

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY . /app

RUN apk add --no-cache postgresql-client build-base postgresql-dev && \
    pip3 install -r requirements.txt

EXPOSE 8000

CMD ["sh", "-c", "python3 manage.py migrate && python3 manage.py runserver 0.0.0.0:8000"]
