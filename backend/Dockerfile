# One image, three roles (see docker-entrypoint.sh): api | worker | migrate.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# WeasyPrint's native libraries (PDF_ENGINE=weasyprint) + a font so PDFs and QR
# captions have glyphs. Everything else (psycopg, zxing-cpp, Pillow) ships
# self-contained wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libgdk-pixbuf-2.0-0 \
        shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# Dependencies first, from pyproject.toml alone, so editing application code
# doesn't invalidate this (slow) layer.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --system --uid 10001 --home-dir /srv simple_erp \
    && mkdir -p /data/documents \
    && chown -R simple_erp:simple_erp /srv /data
USER simple_erp

ENV PORT=8000 \
    DOCUMENT_LOCAL_DIR=/data/documents

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["api"]
