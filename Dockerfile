# Stage 1: Build frontend
FROM node:22-slim AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
WORKDIR /app

# System dependencies for lxml
RUN apt-get update && \
    apt-get install -y --no-install-recommends libxml2 libxslt1.1 && \
    rm -rf /var/lib/apt/lists/*

# Install Python package
COPY pyproject.toml ./
COPY poc/ ./poc/
RUN pip install --no-cache-dir .

# Copy built frontend into place
COPY --from=frontend-builder /build/dist ./frontend/dist/

# Create data and credentials directories
RUN mkdir -p /app/data /app/credentials

EXPOSE 8000

ENTRYPOINT ["python", "-m", "poc", "serve", "--host", "0.0.0.0", "--port", "8000"]
