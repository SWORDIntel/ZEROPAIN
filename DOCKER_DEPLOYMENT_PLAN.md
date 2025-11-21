# ZeroPain Docker Deployment Plan
## Production-Ready VPS Deployment with Caddy

---

## 🎯 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        INTERNET                              │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS (443)
                     ▼
        ┌────────────────────────────┐
        │   CADDY REVERSE PROXY      │
        │  - Auto HTTPS/TLS          │
        │  - Basic Auth              │
        │  - Rate Limiting           │
        │  - Security Headers        │
        └─────┬──────────────┬───────┘
              │              │
    /api/*    │              │    /*
              ▼              ▼
    ┌──────────────┐  ┌──────────────┐
    │   FASTAPI    │  │  REACT SPA   │
    │   Backend    │  │   Frontend   │
    │   Port 8000  │  │   Port 3000  │
    └──────┬───────┘  └──────────────┘
           │
           ├──────────┬──────────┬─────────────┐
           ▼          ▼          ▼             ▼
    ┌──────────┐ ┌────────┐ ┌────────┐  ┌──────────┐
    │PostgreSQL│ │ Redis  │ │ Volume │  │  Intel   │
    │ Database │ │ Cache  │ │ /data  │  │ NPU/GPU  │
    └──────────┘ └────────┘ └────────┘  └──────────┘
```

---

## 📦 Docker Services

### 1. **zeropain-api** (FastAPI Backend)
- Python 3.11 slim base
- Multi-stage build (build deps → runtime)
- Health checks
- Auto-restart
- Environment variables from .env
- Volume mounts: /data, /results

### 2. **zeropain-web** (React Frontend)
- Node 20 for build
- Nginx for serving
- Optimized production build
- TEMPEST theme
- WebSocket proxy support

### 3. **caddy** (Reverse Proxy)
- Automatic HTTPS with Let's Encrypt
- Basic authentication
- Rate limiting (100 req/min)
- Security headers (HSTS, CSP, X-Frame-Options)
- Access logs
- Gzip compression

### 4. **postgres** (Database)
- PostgreSQL 15
- Persistent volume
- Automatic backups
- Health checks
- Initial schema migration

### 5. **redis** (Cache & Sessions)
- Redis 7
- Session storage
- API response caching
- Job queue backend

---

## 🔐 Security Features

### Authentication & Authorization
- JWT tokens (access + refresh)
- bcrypt password hashing
- API key support for programmatic access
- Role-based access control (admin, user, readonly)
- Session management with Redis

### Network Security
- All services on internal network
- Only Caddy exposed to internet
- HTTPS everywhere (internal TLS optional)
- Rate limiting per IP
- DDoS protection via Caddy

### Security Headers
```
Strict-Transport-Security: max-age=31536000
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Content-Security-Policy: default-src 'self'
Referrer-Policy: no-referrer
Permissions-Policy: geolocation=(), microphone=()
```

### Data Security
- Database encryption at rest
- Encrypted environment variables
- Secrets management with Docker secrets
- No hardcoded credentials
- Secure random token generation

---

## 🎨 React Frontend Features

### Core Components
```
src/
├── components/
│   ├── Auth/
│   │   ├── Login.jsx
│   │   └── ProtectedRoute.jsx
│   ├── Dashboard/
│   │   ├── Dashboard.jsx
│   │   ├── SystemStatus.jsx
│   │   └── QuickActions.jsx
│   ├── Compounds/
│   │   ├── CompoundBrowser.jsx
│   │   ├── CompoundCard.jsx
│   │   ├── MoleculeViewer3D.jsx
│   │   └── CompoundEditor.jsx
│   ├── Docking/
│   │   ├── DockingInterface.jsx
│   │   ├── DockingResults.jsx
│   │   └── JobMonitor.jsx
│   ├── Analysis/
│   │   ├── ADMETDashboard.jsx
│   │   ├── ToxicityReport.jsx
│   │   └── Charts.jsx
│   └── Common/
│       ├── Header.jsx
│       ├── Sidebar.jsx
│       ├── Loading.jsx
│       └── ErrorBoundary.jsx
├── hooks/
│   ├── useAuth.js
│   ├── useWebSocket.js
│   └── useAPI.js
├── services/
│   ├── api.js
│   ├── auth.js
│   └── websocket.js
├── styles/
│   └── tempest.css
└── App.jsx
```

### Libraries
- **React 18** - UI framework
- **React Router 6** - Navigation
- **3Dmol.js** - Molecular visualization
- **Recharts** - Data visualization
- **Axios** - HTTP client
- **React Query** - Data fetching/caching
- **Zustand** - State management
- **Framer Motion** - Animations
- **React Hook Form** - Form handling
- **Zod** - Validation

---

## 🚀 Deployment Workflow

### One-Command Deployment
```bash
./deploy.sh production yourdomain.com
```

### Manual Steps
```bash
# 1. Clone and configure
git clone https://github.com/SWORDIntel/ZEROPAIN.git
cd ZEROPAIN
cp .env.example .env
nano .env  # Configure

# 2. Build and start
docker-compose up -d --build

# 3. Initialize database
docker-compose exec api python scripts/init_db.py

# 4. Create admin user
docker-compose exec api python scripts/create_user.py admin

# 5. Access
https://yourdomain.com
```

---

## 📁 File Structure

```
ZEROPAIN/
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.web
│   ├── nginx.conf
│   └── init-db.sql
├── docker-compose.yml
├── docker-compose.prod.yml
├── Caddyfile
├── .env.example
├── .dockerignore
├── deploy.sh
├── backup.sh
└── zeropain/
    ├── api/
    │   ├── main.py
    │   ├── auth.py
    │   ├── middleware.py
    │   └── ...
    └── web/
        └── frontend/
            ├── package.json
            ├── vite.config.js
            └── src/
```

---

## ⚙️ Configuration

### Environment Variables (.env)
```bash
# Application
APP_ENV=production
APP_SECRET_KEY=<generate-random-64-char>
DOMAIN=zeropain.yourdomain.com

# Database
POSTGRES_DB=zeropain
POSTGRES_USER=zeropain
POSTGRES_PASSWORD=<secure-password>
DATABASE_URL=postgresql://zeropain:password@postgres:5432/zeropain

# Redis
REDIS_URL=redis://redis:6379/0

# Auth
JWT_SECRET_KEY=<generate-random-64-char>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Caddy
CADDY_ADMIN_USER=admin
CADDY_ADMIN_PASSWORD=<bcrypt-hash>

# Intel
USE_INTEL_ACCELERATION=true
OPENVINO_DEVICE=AUTO

# Email (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=notifications@zeropain.com
SMTP_PASSWORD=<app-password>
```

### Caddy Configuration
```caddy
{domain} {
    # Automatic HTTPS
    tls {
        protocols tls1.2 tls1.3
    }

    # Basic auth for sensitive endpoints
    basicauth /api/admin/* {
        admin $2a$14$...
    }

    # Rate limiting
    rate_limit {
        zone api {
            key {remote_host}
            events 100
            window 1m
        }
    }

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000"
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
        Content-Security-Policy "default-src 'self'"
        -Server
    }

    # API proxy
    reverse_proxy /api/* zeropain-api:8000
    reverse_proxy /ws/* zeropain-api:8000

    # Frontend
    reverse_proxy zeropain-web:80
}
```

---

## 📊 Monitoring & Logs

### Health Checks
- API: `GET /api/health`
- Database: PostgreSQL connection
- Redis: Ping command
- Caddy: Admin API

### Logging
```bash
# View logs
docker-compose logs -f api
docker-compose logs -f web
docker-compose logs -f caddy

# Export logs
docker-compose logs --since 24h > logs.txt
```

### Metrics
- Prometheus endpoint: `/api/metrics`
- Grafana dashboard (optional)
- Resource usage via Docker stats

---

## 🔄 Backup & Recovery

### Automated Backups
```bash
# Backup script (runs daily via cron)
./backup.sh

# Manual backup
docker-compose exec postgres pg_dump -U zeropain zeropain > backup.sql

# Restore
docker-compose exec -T postgres psql -U zeropain zeropain < backup.sql
```

### Data Volumes
- `zeropain_data` - Application data
- `zeropain_postgres` - Database
- `zeropain_redis` - Cache/sessions
- `zeropain_caddy` - TLS certificates

---

## 🔧 Maintenance

### Updates
```bash
# Update containers
git pull
docker-compose pull
docker-compose up -d --build

# Database migrations
docker-compose exec api alembic upgrade head
```

### Scaling
```bash
# Scale API workers
docker-compose up -d --scale api=3

# Load balancer (Caddy handles automatically)
```

---

## 📈 Performance Optimization

### Frontend
- Code splitting
- Lazy loading
- Image optimization
- Service worker caching
- CDN for static assets (optional)

### Backend
- Redis caching
- Database connection pooling
- Async I/O
- Multiprocessing for CPU tasks
- Intel NPU/GPU acceleration

### Network
- Gzip compression
- HTTP/2 support
- Brotli compression
- CDN integration

---

## 🎯 Success Criteria

- ✅ One-command deployment
- ✅ HTTPS with automatic renewal
- ✅ Authentication and authorization
- ✅ Real-time WebSocket updates
- ✅ 3D molecule visualization
- ✅ Responsive on mobile/tablet/desktop
- ✅ < 100ms API response time
- ✅ 99.9% uptime
- ✅ Automated backups
- ✅ Security headers A+ rating
- ✅ OWASP compliance

---

**Ready to execute this plan!**
