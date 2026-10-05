# Web image: multi-stage, Next.js standalone output, non-root.
FROM node:22-slim AS base
RUN corepack enable
WORKDIR /app

FROM base AS build
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-slim
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
RUN useradd --system --uid 10001 --create-home tss
COPY --from=build --chown=tss /app/.next/standalone ./
COPY --from=build --chown=tss /app/.next/static ./.next/static
COPY --from=build --chown=tss /app/public ./public
USER tss
EXPOSE 3000
CMD ["node", "server.js"]
