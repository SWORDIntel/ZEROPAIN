# ZeroPain Web Security Layer Dependencies
# =========================================

# Core Web Framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
aiofiles>=23.2.1

# Security & Authentication
cryptography>=41.0.7
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-fido2>=1.1.2  # YubiKey/FIDO2 support
pyotp>=2.9.0  # TOTP/HOTP support

# Rate Limiting & Protection
slowapi>=0.1.9
redis>=5.0.1
python-redis-lock>=4.0.0

# Session Management
starlette-session>=0.4.3
itsdangerous>=2.1.2

# Database
sqlalchemy>=2.0.23
alembic>=1.13.0
psycopg2-binary>=2.9.9  # PostgreSQL
sqlite3  # Built-in

# HTTP & Networking
httpx>=0.25.2
aiohttp>=3.9.1
websockets>=12.0

# Monitoring & Logging
prometheus-client>=0.19.0
python-json-logger>=2.0.7
structlog>=23.2.0

# Deception & Honeypot
faker>=20.1.0  # Generate fake data
mimesis>=12.1.0  # Alternative fake data generator

# Security Scanning (optional)
bandit>=1.7.5
safety>=3.0.1

# Development & Testing
pytest>=7.4.3
pytest-asyncio>=0.21.1
pytest-cov>=4.1.0
httpx-mock>=0.4.0
respx>=0.20.2

# SSL/TLS Certificate Generation
pyOpenSSL>=23.3.0
certifi>=2023.11.17

# Environment & Configuration
python-dotenv>=1.0.0
pydantic-settings>=2.1.0

# Additional PsyOps Tools
user-agents>=2.2.0  # Fake user agent generation
pyperclip>=1.8.2  # Clipboard manipulation (for confusion)

# Performance
orjson>=3.9.10  # Fast JSON
ujson>=5.9.0  # Alternative fast JSON
msgpack>=1.0.7  # Binary serialization

# Optional Advanced Features
# Uncomment if using these features:

# celery>=5.3.4  # Task queue for background jobs
# flower>=2.0.1  # Celery monitoring
# dramatiq>=1.15.0  # Alternative task queue
# apscheduler>=3.10.4  # Job scheduling

# Machine Learning for Attack Detection (optional)
# scikit-learn>=1.3.2
# tensorflow>=2.15.0
# xgboost>=2.0.2

# GeoIP for location-based blocking
# geoip2>=4.8.0
# maxminddb>=2.5.1

# WAF Integration
# py-modsecurity>=0.1.0  # ModSecurity Python bindings

# Cloud Provider SDKs (if deploying to cloud)
# boto3>=1.34.0  # AWS
# azure-identity>=1.15.0  # Azure
# google-cloud-secret-manager>=2.17.0  # GCP