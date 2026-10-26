# RedGuard backend: FastAPI + Mode A scanner + Mode B lab, with the Prisma
# client and its engines baked in so the container needs no network to start.
#
# Build context is the repository root (core/ is a sibling of backend/).

# Prisma's Python CLI drives the Node-based Prisma CLI. Left to itself it
# downloads the newest Node release at build time — unpinned, and (Node 26)
# linked against libatomic, which slim images lack, so `prisma generate`
# failed. Copy the same pinned Node the frontend image uses instead.
FROM node:22-slim AS node

FROM python:3.12-slim
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# openssl: Prisma's query/schema engines link against it.
# git: lets the reproducibility stamp read the commit when the repo is
#      bind-mounted (docker-compose.dev.yml); harmless otherwise.
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssl git \
 && rm -rf /var/lib/apt/lists/* \
 && git config --global --add safe.directory /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app/backend

# requirements.txt is the readable list; requirements.lock pins every package in the tested environment.
COPY backend/requirements.txt backend/requirements.lock ./
RUN pip install -r requirements.txt -c requirements.lock

# Generate the client and fetch every engine now, so `prisma db push` in the
# entrypoint works offline.
COPY backend/prisma/schema.prisma ./prisma/schema.prisma
RUN prisma generate --schema prisma/schema.prisma && prisma py fetch

COPY core /app/core
COPY backend /app/backend
COPY docker/backend-entrypoint.sh /usr/local/bin/redguard-entrypoint
RUN chmod +x /usr/local/bin/redguard-entrypoint

# The commit this image was built from. There is no .git inside the image,
# so the Mode B reproducibility stamp falls back to this.
ARG GIT_COMMIT=""
ENV REDGUARD_GIT_COMMIT=${GIT_COMMIT}

# The database lives on a volume, never in the image's copy of the
# committed seed file (CLAUDE.md: backend/prisma/dev.db is demo data).
ENV DATABASE_URL=file:/data/redguard.db
VOLUME ["/data"]

EXPOSE 8000
ENTRYPOINT ["redguard-entrypoint"]
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
