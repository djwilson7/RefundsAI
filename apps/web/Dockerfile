FROM node:24-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci --workspace @refunds-ai/web

FROM node:24-alpine AS builder
WORKDIR /app
ARG REFUNDS_AI_DEMO_MODE=true
ENV REFUNDS_AI_DEMO_MODE=$REFUNDS_AI_DEMO_MODE

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run web:build

FROM deps AS development
WORKDIR /app

ENV NODE_ENV=development
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
ENV NEXT_TELEMETRY_DISABLED=1

COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev", "--workspace", "@refunds-ai/web", "--", "--webpack", "--hostname", "0.0.0.0"]

FROM node:24-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/apps/web/public ./apps/web/public
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/.next/standalone ./

EXPOSE 3000
CMD ["node", "apps/web/server.js"]
