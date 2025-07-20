#!/bin/bash

# Home.ai Production Deployment Script
# This script sets up and deploys the home.ai application in production

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root"
   exit 1
fi

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

print_status "Starting Home.ai production deployment..."

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    print_warning ".env file not found. Creating default .env file..."
    cat > "$ENV_FILE" << EOF
# Home.ai Production Environment Variables
# Change these values for production use

# Flask
SECRET_KEY=$(openssl rand -hex 32)
FLASK_ENV=production

# MongoDB
MONGO_ROOT_PASSWORD=$(openssl rand -base64 32)

# MinIO
MINIO_ACCESS_KEY=$(openssl rand -base64 16)
MINIO_SECRET_KEY=$(openssl rand -base64 32)

# Admin
ADMIN_PASSWORD=$(openssl rand -base64 12)

# Server
HOST=0.0.0.0
PORT=5001

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/home-ai/app.log
EOF
    print_success "Created .env file with secure random values"
    print_warning "Please review and update the .env file with your preferred values"
fi

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    print_status "Loading environment variables..."
    export $(cat "$ENV_FILE" | grep -v '^#' | xargs)
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/ssl"

# Generate self-signed SSL certificate for development
if [ ! -f "$PROJECT_DIR/ssl/cert.pem" ] || [ ! -f "$PROJECT_DIR/ssl/key.pem" ]; then
    print_status "Generating self-signed SSL certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$PROJECT_DIR/ssl/key.pem" \
        -out "$PROJECT_DIR/ssl/cert.pem" \
        -subj "/C=AT/ST=Vienna/L=Vienna/O=Home.ai/CN=localhost"
    print_success "SSL certificate generated"
fi

# Build and start services
print_status "Building and starting services..."
cd "$PROJECT_DIR"

# Stop existing containers
print_status "Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down --remove-orphans

# Build and start
print_status "Building Docker images..."
docker-compose -f docker-compose.prod.yml build

print_status "Starting services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 30

# Check service health
print_status "Checking service health..."

# Check MongoDB
if docker-compose -f docker-compose.prod.yml exec -T mongodb mongosh --eval "db.runCommand('ping')" > /dev/null 2>&1; then
    print_success "MongoDB is running"
else
    print_error "MongoDB is not responding"
    exit 1
fi

# Check MinIO
if curl -f http://localhost:9001/minio/health/live > /dev/null 2>&1; then
    print_success "MinIO is running"
else
    print_error "MinIO is not responding"
    exit 1
fi

# Check Home.ai application
if curl -f http://localhost:5001/api/stats > /dev/null 2>&1; then
    print_success "Home.ai application is running"
else
    print_error "Home.ai application is not responding"
    exit 1
fi

# Show service status
print_status "Service status:"
docker-compose -f docker-compose.prod.yml ps

# Show access information
print_success "Deployment completed successfully!"
echo
echo "Access Information:"
echo "=================="
echo "Home.ai Application: http://localhost:5001"
echo "MinIO Console: http://localhost:9001"
echo "MongoDB: localhost:27017"
echo
echo "Default Credentials:"
echo "==================="
echo "Admin Username: admin"
echo "Admin Password: $ADMIN_PASSWORD"
echo
echo "MinIO Access Key: $MINIO_ACCESS_KEY"
echo "MinIO Secret Key: $MINIO_SECRET_KEY"
echo
echo "Useful Commands:"
echo "==============="
echo "View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "Stop services: docker-compose -f docker-compose.prod.yml down"
echo "Restart services: docker-compose -f docker-compose.prod.yml restart"
echo "Update application: ./deploy.sh"
echo
print_warning "Remember to change default passwords in production!" 