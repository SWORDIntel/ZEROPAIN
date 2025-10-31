# ZeroPain Therapeutics Security Stack
# Docker Compose configuration for the psychological operations defense system
# ==============================================================================

version: '3.9'

services:
  # ==============================================================================
  # NGINX REVERSE PROXY WITH MODSECURITY WAF
  # ==============================================================================
  nginx:
    image: owasp/modsecurity-crs:nginx-alpine
    container_name: zeropain-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/modsecurity.conf:/etc/nginx/modsecurity/modsecurity.conf:ro
      - ./nginx/crs-setup.conf:/etc/nginx/modsecurity/crs-setup.conf:ro
      - ./certs:/etc/nginx/certs:ro
      - nginx-logs:/var/log/nginx
      - ./honeypot/fake-files:/usr/share/nginx/honeypot:ro
    environment:
      - PARANOIA_LEVEL=3
      - ANOMALY_INBOUND=5
      - ANOMALY_OUTBOUND=4
      - BACKEND=http://zeropain-web:8443
    networks:
      - zeropain-dmz
      - zeropain-internal
    depends_on:
      - zeropain-web
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 512M
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ==============================================================================
  # MAIN WEB APPLICATION WITH PSYOPS
  # ==============================================================================
  zeropain-web:
    build:
      context: .
      dockerfile: Dockerfile.security
    container_name: zeropain-web
    restart: always
    environment:
      - DATABASE_URL=postgresql://zeropain:${DB_PASSWORD}@postgres:5432/zeropain_security
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - DOMAIN=zeropain-therapeutics.local
      - YUBIKEY_APP_ID=${YUBIKEY_APP_ID}
      - YUBIKEY_CLIENT_ID=${YUBIKEY_CLIENT_ID}
      - TARPIT_MIN_DELAY=0.5
      - TARPIT_MAX_DELAY=30.0
      - HONEYPOT_MODE=aggressive
      - DECEPTION_LEVEL=maximum
    volumes:
      - ./app:/app:ro
      - ./logs:/app/logs
      - yubikey-db:/app/data
    networks:
      - zeropain-internal
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '4'
          memory: 2G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8443/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ==============================================================================
  # POSTGRESQL DATABASE
  # ==============================================================================
  postgres:
    image: postgres:15-alpine
    container_name: zeropain-postgres
    restart: always
    environment:
      - POSTGRES_DB=zeropain_security
      - POSTGRES_USER=zeropain
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    networks:
      - zeropain-internal
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U zeropain"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ==============================================================================
  # REDIS CACHE & SESSION STORE
  # ==============================================================================
  redis:
    image: redis:7-alpine
    container_name: zeropain-redis
    restart: always
    command: >
      redis-server
      --requirepass ${REDIS_PASSWORD}
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
      --tcp-backlog 511
      --tcp-keepalive 60
      --timeout 0
    volumes:
      - redis-data:/data
    networks:
      - zeropain-internal
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ==============================================================================
  # HONEYPOT FILE GENERATOR
  # ==============================================================================
  honeypot-generator:
    build:
      context: .
      dockerfile: Dockerfile.honeypot
    container_name: zeropain-honeypot
    restart: always
    environment:
      - GENERATION_INTERVAL=3600
      - FILE_TYPES=medical,financial,research,proprietary
      - CORRUPTION_LEVEL=high
      - DECEPTION_MODE=maximum
    volumes:
      - ./honeypot/fake-files:/output
      - ./honeypot/templates:/templates:ro
    networks:
      - zeropain-internal
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  # ==============================================================================
  # INTRUSION DETECTION SYSTEM (SURICATA)
  # ==============================================================================
  suricata:
    image: jasonish/suricata:latest
    container_name: zeropain-ids
    restart: always
    network_mode: host
    cap_add:
      - NET_ADMIN
      - NET_RAW
      - SYS_NICE
    volumes:
      - ./suricata/suricata.yaml:/etc/suricata/suricata.yaml:ro
      - ./suricata/rules:/var/lib/suricata/rules:ro
      - suricata-logs:/var/log/suricata
    command: -i eth0
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 1G

  # ==============================================================================
  # LOG AGGREGATION (LOKI)
  # ==============================================================================
  loki:
    image: grafana/loki:latest
    container_name: zeropain-loki
    restart: always
    ports:
      - "3100:3100"
    volumes:
      - ./loki/loki-config.yaml:/etc/loki/local-config.yaml:ro
      - loki-data:/loki
    networks:
      - zeropain-internal
    command: -config.file=/etc/loki/local-config.yaml
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

  # ==============================================================================
  # PROMTAIL (LOG SHIPPER)
  # ==============================================================================
  promtail:
    image: grafana/promtail:latest
    container_name: zeropain-promtail
    restart: always
    volumes:
      - ./promtail/promtail-config.yaml:/etc/promtail/config.yml:ro
      - nginx-logs:/var/log/nginx:ro
      - ./logs:/var/log/zeropain:ro
      - suricata-logs:/var/log/suricata:ro
      - /var/log:/var/log/host:ro
    networks:
      - zeropain-internal
    command: -config.file=/etc/promtail/config.yml
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  # ==============================================================================
  # MONITORING (PROMETHEUS)
  # ==============================================================================
  prometheus:
    image: prom/prometheus:latest
    container_name: zeropain-prometheus
    restart: always
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - zeropain-internal
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/usr/share/prometheus/console_libraries'
      - '--web.console.templates=/usr/share/prometheus/consoles'
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

  # ==============================================================================
  # GRAFANA DASHBOARD
  # ==============================================================================
  grafana:
    image: grafana/grafana:latest
    container_name: zeropain-grafana
    restart: always
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=redis-app,redis-datasource
      - GF_SERVER_ROOT_URL=https://zeropain-therapeutics.local/grafana
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    networks:
      - zeropain-internal
    depends_on:
      - prometheus
      - loki
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

  # ==============================================================================
  # SECURITY SCANNER (CONTINUOUS)
  # ==============================================================================
  security-scanner:
    build:
      context: .
      dockerfile: Dockerfile.scanner
    container_name: zeropain-scanner
    restart: always
    environment:
      - SCAN_INTERVAL=300
      - SCAN_TARGETS=nginx,zeropain-web,postgres,redis
      - ALERT_WEBHOOK=${ALERT_WEBHOOK}
    volumes:
      - ./scanner/reports:/reports
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - zeropain-internal
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

# ==============================================================================
# NETWORKS
# ==============================================================================
networks:
  zeropain-dmz:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24
          gateway: 172.20.0.1
    driver_opts:
      com.docker.network.bridge.enable_icc: "false"
      com.docker.network.bridge.enable_ip_masquerade: "true"
      
  zeropain-internal:
    driver: bridge
    internal: true
    ipam:
      config:
        - subnet: 172.21.0.0/24
          gateway: 172.21.0.1
    driver_opts:
      com.docker.network.bridge.enable_icc: "true"
      com.docker.network.bridge.enable_ip_masquerade: "false"

# ==============================================================================
# VOLUMES
# ==============================================================================
volumes:
  postgres-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /var/lib/zeropain/postgres
      
  redis-data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /var/lib/zeropain/redis
      
  yubikey-db:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /var/lib/zeropain/yubikey
      
  nginx-logs:
    driver: local
    
  suricata-logs:
    driver: local
    
  loki-data:
    driver: local
    
  prometheus-data:
    driver: local
    
  grafana-data:
    driver: local

# ==============================================================================
# SECRETS (Use Docker Secrets in production)
# ==============================================================================
# In production, use proper Docker secrets management:
# docker secret create db_password ./secrets/db_password.txt
# docker secret create redis_password ./secrets/redis_password.txt
# docker secret create secret_key ./secrets/secret_key.txt
