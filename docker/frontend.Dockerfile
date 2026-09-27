# RedGuard frontend: Next.js, built as a standalone server.
#
# Build context is the repository root. Stages:
#   deps    — node_modules only (also the base of the dev compose service)
#   build   — `next build` with output: 'standalone'
#   runner  — the minimal server, no node_modules
FROM node:22-slim AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM deps AS build
COPY . .
# Rewrites are resolved at build time, so the backend address is a build
# argument, not a runtime variable.
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=${BACKEND_URL} \
    NEXT_OUTPUT=standalone
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
