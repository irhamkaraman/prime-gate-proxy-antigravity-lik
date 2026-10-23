# ==============================================================================
# Prime Gate Antigravity - Multi-Stage Production Container
# Stage 1: UI Builder (Vite + TypeScript)
# Stage 2: Runtime (Python 3.11-slim + Node.js runtime)
# ==============================================================================

# Stage 1: Build Frontend UI
FROM node:20-alpine AS ui-builder
WORKDIR /app/ui
COPY ui/package*.json ./
RUN npm ci || npm install
COPY ui/ ./
RUN npm run build

# Stage 2: Runtime Container
FROM python:3.11-slim
WORKDIR /app

# Install Node.js (for UI server) and curl (for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Copy pre-compiled UI dist from builder
COPY --from=ui-builder /app/ui/dist /app/ui/dist

# Install Prime Gate CLI in container
RUN pip install --no-cache-dir -e .

# Expose ports
# 52110: Web UI Dashboard
# 52111: OpenAI/Anthropic Compatible Proxy Gateway API
EXPOSE 52110 52111

# Define persistent storage volume for database and account credentials
VOLUME ["/app/data"]

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=52111 \
    UI_PORT=52110

# Entrypoint script
COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://127.0.0.1:52111/health || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
