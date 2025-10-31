# Honeypot File Generator Container
# Generates convincing fake medical and financial data
# =====================================================

FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    libreoffice \
    pandoc \
    wkhtmltopdf \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    faker \
    mimesis \
    openpyxl \
    python-docx \
    reportlab \
    pdfkit \
    pillow \
    cryptography

# Create app directory
WORKDIR /app

# Copy honeypot generator script
COPY --chown=1000:1000 honeypot_generator.py /app/

# Create output directory
RUN mkdir -p /output && chmod 777 /output

# Run as non-root
USER 1000

# Generate files every hour by default
CMD ["python", "honeypot_generator.py"]
