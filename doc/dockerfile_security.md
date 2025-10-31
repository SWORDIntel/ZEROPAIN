# ZeroPain Therapeutics Security Container
# Multi-stage build for minimal attack surface
# ==============================================

# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install
COPY requirements_web_security.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# ==============================================
# Stage 2: Runtime
FROM python:3.11-slim

# Security: Run as non-root user
RUN groupadd -r zeropain && useradd -r -g zeropain -u 1000 zeropain

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application directories
RUN mkdir -p /app /app/logs /app/data /app/certs && \
    chown -R zeropain:zeropain /app

WORKDIR /app

# Copy application code
COPY --chown=zeropain:zeropain zeropain_web_security.py /app/
COPY --chown=zeropain:zeropain yubikey_setup.py /app/

# Security hardening
RUN chmod 750 /app/*.py && \
    chmod 700 /app/data && \
    chmod 755 /app/logs

# Switch to non-root user
USER zeropain

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8443/health || exit 1

# Expose port (internal only)
EXPOSE 8443

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    LOG_LEVEL=INFO

# Security: No shell by default
ENTRYPOINT ["python"]
CMD ["zeropain_web_security.py"]

# Labels
LABEL maintainer="ZeroPain Therapeutics Security Team" \
      version="3.0" \
      description="Psychological Operations Defense System" \
      security.scan="trivy scan --severity HIGH,CRITICAL zeropain-security:latest"
