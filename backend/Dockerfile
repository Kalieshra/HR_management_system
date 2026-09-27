FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System packages:
#   gettext                     -> makemessages / compilemessages (ar + en)
#   libpango*, libharfbuzz, ... -> WeasyPrint (Arabic payslip PDFs, phase 5)
#   fonts-noto-core             -> Arabic glyphs inside generated PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gettext \
        curl \
        libpq5 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libffi8 \
        libjpeg62-turbo \
        libopenjp2-7 \
        shared-mime-info \
        fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

COPY . .

# Run as a uid/gid 1000 user, matching a typical Linux desktop account. This
# service bind-mounts the working tree in development, and a root container
# leaves root-owned media/ and .pytest_cache/ behind that you cannot delete.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --create-home app \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
