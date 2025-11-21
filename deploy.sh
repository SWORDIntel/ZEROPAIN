#!/bin/bash
# ZEROPAIN Deployment Script

set -e

echo "=== ZEROPAIN Docker Deployment ==="

# Check for .env file
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "WARNING: Please edit .env with your production values!"
    echo "Especially: DOMAIN, POSTGRES_PASSWORD, SECRET_KEY"
    exit 1
fi

# Build and start containers
echo "Building Docker images..."
docker-compose build

echo "Starting services..."
docker-compose up -d

echo ""
echo "=== Deployment Complete ==="
echo "Services running:"
docker-compose ps

echo ""
echo "Access the application at: https://\${DOMAIN:-localhost}"
echo ""
echo "Useful commands:"
echo "  docker-compose logs -f        # View logs"
echo "  docker-compose down           # Stop services"
echo "  docker-compose restart api    # Restart API"
