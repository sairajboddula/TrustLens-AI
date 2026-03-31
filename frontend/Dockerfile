# =============================================================================
# KYC Frontend - Multi-stage Dockerfile (Vite + React)
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies first (layer caching)
COPY package.json ./
RUN npm install

# Copy source and build
COPY . .

# VITE_ vars are inlined at build time
ARG VITE_API_URL=http://localhost:8000/api/v1
ARG VITE_APP_NAME=KYC Platform
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_APP_NAME=$VITE_APP_NAME

RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: Production (serve built assets)
# -----------------------------------------------------------------------------
FROM node:20-alpine AS production

RUN npm install -g serve

WORKDIR /app

COPY --from=builder /app/dist .

EXPOSE 3000

# -s: single-page app mode (rewrite all paths to index.html)
CMD ["serve", "-s", ".", "-l", "3000"]
