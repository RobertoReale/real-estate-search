# Multi-arch image for NAS and Raspberry Pi (linux/amd64 + linux/arm64).
#
# Two stages so the runtime image carries no Node: the dashboard is compiled
# once here and copied in as static files, which is the same "ship it prebuilt"
# rule the Windows package follows.

FROM --platform=$BUILDPLATFORM node:20-slim AS frontend
WORKDIR /src
# The lock first, so a source-only change does not re-resolve dependencies.
COPY frontend/package.json frontend/package-lock.json ./
# `ci`, not `install`: it installs exactly what the lock pins and fails if the
# lock and package.json disagree, instead of quietly rewriting the lock.
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

# curl_cffi's TLS impersonation (invariant 8) needs a real libcurl; the slim
# image does not ship the certificate bundle its HTTPS calls verify against.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The product manifest only: pinned and hashed. The dev and packaging sets have
# no business in a runtime image.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY backend/ ./
COPY --from=frontend /src/dist ./frontend/dist

# config.FRONTEND_DIST resolves to BASE_DIR.parent/"frontend"/"dist" outside a
# PyInstaller bundle, so the built app is mounted from one level up.
RUN mkdir -p /frontend && ln -s /app/frontend/dist /frontend/dist

# The database, settings, log and backups live on the volume, never in the
# image layer - a `docker compose pull` would otherwise discard them.
ENV APP_DATA_DIR=/data
VOLUME ["/data"]

# Inside a container this is the container's own interface, not the host's: the
# network namespace is the boundary, and docker-compose.yml publishes the port
# to loopback only. Invariant 14's rule - never expose the unauthenticated API
# by default - is enforced there, by the port mapping.
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000
EXPOSE 8000

CMD ["python", "run.py"]
