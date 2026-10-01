FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Static files are baked into the image (served by WhiteNoise).
RUN SECRET_KEY=build-only DEBUG=False python manage.py collectstatic --noinput \
    && useradd --create-home --uid 1000 app && chown -R app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=4).status == 200 else 1)"

# Migrations run on start so a fresh database (or a new release) is always in sync.
# Uvicorn serves the ASGI app: regular HTTP plus WebSockets (/ws/).
CMD ["sh", "-c", "python manage.py migrate --noinput && uvicorn ticket_system.asgi:application --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-3} --proxy-headers --forwarded-allow-ips='*'"]
