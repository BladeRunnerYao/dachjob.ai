FROM node:26-alpine AS deps

WORKDIR /app

COPY app/frontend/package*.json ./
RUN npm ci

FROM node:26-alpine AS builder

WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY --from=deps /app/node_modules ./node_modules
COPY app/frontend/ .
RUN npm run build

FROM node:26-alpine AS prod-deps

WORKDIR /app

COPY app/frontend/package*.json ./
RUN npm ci --omit=dev

FROM node:26-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ARG NEXT_PUBLIC_API_BASE_URL=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

COPY --from=prod-deps --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/package*.json ./

USER nextjs

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0"]
