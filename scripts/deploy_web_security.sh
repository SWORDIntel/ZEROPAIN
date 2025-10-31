#!/bin/bash

# ==============================================================================
# ZeroPain Web Security Deployment Script
# Deploys the psychological operations security layer
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# ASCII Banner
echo -e "${CYAN}"
cat << "EOF"
╔════════════════════════════════════════════════════════════════╗
║     ZEROPAIN THERAPEUTICS - SECURITY DEPLOYMENT SYSTEM        ║
║           Psychological Operations Defense Layer              ║
╚════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# Configuration
DOMAIN="zeropain-therapeutics.local"
PORT=8443
WORKERS=4
VENV_NAME="zeropain_security_env"

# Check if running as root (required for some operations)
if [[ $EUID -eq 0 ]]; then
   echo -e "${YELLOW}⚠ Running as root - good for system config${NC}"
else
   echo -e "${YELLOW}⚠ Not running as root - some features may require sudo${NC}"
fi

# Step 1: System Dependencies
echo -e "${BLUE}[1/10] Installing system dependencies...${NC}"

if command -v apt-get &> /dev/null; then
    # Debian/Ubuntu
    sudo apt-get update
    sudo apt-get install -y \
        python3.10 python3.10-venv python3-pip \
        nginx redis-server postgresql \
        build-essential libssl-dev libffi-dev \
        fail2ban ufw \
        certbot python3-certbot-nginx
elif command -v yum &> /dev/null; then
    # RHEL/CentOS
    sudo yum install -y \
        python3 python3-pip \
        nginx redis postgresql-server \
        gcc openssl-devel \
        fail2ban firewalld \
        certbot python3-certbot-nginx
else
    echo -e "${RED}✗ Unsupported system. Install dependencies manually.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ System dependencies installed${NC}"

# Step 2: Create application directory
echo -e "${BLUE}[2/10] Setting up application directory...${NC}"

APP_DIR="/opt/zeropain_security"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR
cd $APP_DIR

# Copy application files
cp zeropain_web_security.py $APP_DIR/
cp requirements_web_security.txt $APP_DIR/requirements.txt

echo -e "${GREEN}✓ Application directory ready${NC}"

# Step 3: Python virtual environment
echo -e "${BLUE}[3/10] Creating Python virtual environment...${NC}"

python3 -m venv $VENV_NAME
source $VENV_NAME/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo -e "${GREEN}✓ Python environment configured${NC}"

# Step 4: Generate SSL certificates
echo -e "${BLUE}[4/10] Generating SSL certificates...${NC}"

mkdir -p certs
cd certs

if [ ! -f "cert.pem" ]; then
    # Generate self-signed certificate for testing
    openssl req -x509 -newkey rsa:4096 -nodes \
        -out cert.pem -keyout key.pem -days 365 \
        -subj "/C=US/ST=State/L=City/O=ZeroPain Therapeutics/CN=$DOMAIN"
    
    # Generate Diffie-Hellman parameters for extra security
    openssl dhparam -out dhparam.pem 2048
    
    echo -e "${GREEN}✓ SSL certificates generated${NC}"
else
    echo -e "${YELLOW}⚠ SSL certificates already exist${NC}"
fi

cd ..

# Step 5: Configure PostgreSQL database
echo -e "${BLUE}[5/10] Configuring PostgreSQL database...${NC}"

# Start PostgreSQL if not running
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE zeropain_security;
CREATE USER zeropain_user WITH ENCRYPTED PASSWORD 'ultra_secure_password_change_me';
GRANT ALL PRIVILEGES ON DATABASE zeropain_security TO zeropain_user;
EOF

echo -e "${GREEN}✓ Database configured${NC}"

# Step 6: Configure Redis
echo -e "${BLUE}[6/10] Configuring Redis...${NC}"

# Secure Redis configuration
sudo tee /etc/redis/redis.conf.d/security.conf > /dev/null << EOF
# Security hardening
bind 127.0.0.1 ::1
protected-mode yes
port 6379
requirepass ultra_secure_redis_password_change_me
maxmemory 256mb
maxmemory-policy allkeys-lru
EOF

sudo systemctl restart redis-server
sudo systemctl enable redis-server

echo -e "${GREEN}✓ Redis configured${NC}"

# Step 7: Configure Nginx reverse proxy
echo -e "${BLUE}[7/10] Configuring Nginx...${NC}"

sudo tee /etc/nginx/sites-available/zeropain_security > /dev/null << EOF
# Rate limiting zones
limit_req_zone \$binary_remote_addr zone=general:10m rate=10r/s;
limit_req_zone \$binary_remote_addr zone=api:10m rate=5r/s;
limit_req_zone \$binary_remote_addr zone=auth:10m rate=2r/s;
limit_conn_zone \$binary_remote_addr zone=addr:10m;

# Upstream backend
upstream zeropain_backend {
    least_conn;
    server 127.0.0.1:8443 weight=1 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8444 weight=1 max_fails=3 fail_timeout=30s backup;
    keepalive 32;
}

server {
    listen 80;
    server_name $DOMAIN;
    
    # Redirect all HTTP to HTTPS
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    # SSL Configuration
    ssl_certificate $APP_DIR/certs/cert.pem;
    ssl_certificate_key $APP_DIR/certs/key.pem;
    ssl_dhparam $APP_DIR/certs/dhparam.pem;
    
    # Strong SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer" always;
    
    # Hide server info
    server_tokens off;
    more_clear_headers Server;
    
    # Connection limits
    limit_conn addr 10;
    limit_req zone=general burst=20 nodelay;
    
    # Client body limits
    client_body_buffer_size 1K;
    client_header_buffer_size 1k;
    client_max_body_size 1M;
    large_client_header_buffers 2 1k;
    
    # Timeouts
    client_body_timeout 10;
    client_header_timeout 10;
    keepalive_timeout 5 5;
    send_timeout 10;
    
    # Proxy to backend
    location / {
        # Apply rate limiting
        limit_req zone=general burst=10 nodelay;
        
        proxy_pass https://zeropain_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering
        proxy_buffering off;
    }
    
    # API endpoints with stricter limits
    location /api/ {
        limit_req zone=api burst=5 nodelay;
        proxy_pass https://zeropain_backend;
    }
    
    # Auth endpoints with very strict limits
    location /api/auth/ {
        limit_req zone=auth burst=2 nodelay;
        proxy_pass https://zeropain_backend;
    }
    
    # Block common attack paths
    location ~ /\.(git|env|htaccess|htpasswd) {
        return 444;  # Close connection without response
    }
    
    # Custom error pages
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
}
EOF

sudo ln -sf /etc/nginx/sites-available/zeropain_security /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

echo -e "${GREEN}✓ Nginx configured${NC}"

# Step 8: Configure firewall
echo -e "${BLUE}[8/10] Configuring firewall...${NC}"

if command -v ufw &> /dev/null; then
    # UFW (Ubuntu)
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow ssh
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw --force enable
elif command -v firewall-cmd &> /dev/null; then
    # Firewalld (RHEL/CentOS)
    sudo firewall-cmd --permanent --add-service=ssh
    sudo firewall-cmd --permanent --add-service=http
    sudo firewall-cmd --permanent --add-service=https
    sudo firewall-cmd --reload
fi

echo -e "${GREEN}✓ Firewall configured${NC}"

# Step 9: Configure Fail2Ban
echo -e "${BLUE}[9/10] Configuring Fail2Ban...${NC}"

sudo tee /etc/fail2ban/jail.d/zeropain.conf > /dev/null << EOF
[zeropain-auth]
enabled = true
filter = zeropain-auth
logpath = $APP_DIR/logs/zeropain_security.log
maxretry = 3
findtime = 600
bantime = 3600
action = iptables-multiport[name=zeropain, port="80,443"]

[zeropain-honeypot]
enabled = true
filter = zeropain-honeypot
logpath = $APP_DIR/logs/zeropain_security.log
maxretry = 1
findtime = 86400
bantime = 604800
action = iptables-multiport[name=honeypot, port="80,443"]
EOF

# Create filter rules
sudo tee /etc/fail2ban/filter.d/zeropain-auth.conf > /dev/null << EOF
[Definition]
failregex = Authentication failed for .* from <HOST>
ignoreregex =
EOF

sudo tee /etc/fail2ban/filter.d/zeropain-honeypot.conf > /dev/null << EOF
[Definition]
failregex = Honeypot triggered by <HOST>
ignoreregex =
EOF

sudo systemctl restart fail2ban
sudo systemctl enable fail2ban

echo -e "${GREEN}✓ Fail2Ban configured${NC}"

# Step 10: Create systemd service
echo -e "${BLUE}[10/10] Creating systemd service...${NC}"

sudo tee /etc/systemd/system/zeropain-security.service > /dev/null << EOF
[Unit]
Description=ZeroPain Security Layer
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=exec
User=$USER
Group=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/$VENV_NAME/bin"
ExecStart=$APP_DIR/$VENV_NAME/bin/python $APP_DIR/zeropain_web_security.py
Restart=always
RestartSec=5
StandardOutput=append:$APP_DIR/logs/service.log
StandardError=append:$APP_DIR/logs/error.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$APP_DIR
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictSUIDSGID=true
LockPersonality=true

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
mkdir -p $APP_DIR/logs

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable zeropain-security
sudo systemctl start zeropain-security

echo -e "${GREEN}✓ Systemd service created${NC}"

# Final status check
echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${GREEN}    DEPLOYMENT COMPLETE!${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo -e "${YELLOW}Service Status:${NC}"
sudo systemctl status zeropain-security --no-pager | head -n 10
echo ""
echo -e "${YELLOW}Access Points:${NC}"
echo -e "  HTTPS: https://$DOMAIN"
echo -e "  HTTP:  http://$DOMAIN (redirects to HTTPS)"
echo ""
echo -e "${YELLOW}Security Features Active:${NC}"
echo -e "  ✓ SSL/TLS encryption"
echo -e "  ✓ Rate limiting"
echo -e "  ✓ Fail2Ban protection"
echo -e "  ✓ Firewall rules"
echo -e "  ✓ Tarpit system"
echo -e "  ✓ Honeypot paths"
echo -e "  ✓ YubiKey authentication"
echo ""
echo -e "${RED}IMPORTANT:${NC}"
echo -e "1. Change default passwords in configuration files"
echo -e "2. Register YubiKey for authentication"
echo -e "3. Configure DNS to point to this server"
echo -e "4. Consider getting real SSL certificate with Let's Encrypt"
echo ""
echo -e "${GREEN}Happy hunting, attackers! 🎯${NC}"
