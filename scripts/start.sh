#!/bin/bash
# Start script for GTO Poker Solver

set -e

echo "🚀 Starting GTO Poker Solver..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Vérifier les fichiers frontend avant de démarrer
if [ -f "./scripts/check-frontend.sh" ]; then
    print_status "Vérification des fichiers frontend..."
    if ! ./scripts/check-frontend.sh; then
        print_error "Problème avec les fichiers frontend. Veuillez résoudre les problèmes avant de démarrer."
        exit 1
    fi
else
    print_warning "Script de vérification des fichiers frontend non trouvé. Ignoré."
fi

# Parse command line arguments
ENVIRONMENT="production"
SCALE_COMPUTE_NODES=2

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--scale)
            SCALE_COMPUTE_NODES="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -e, --environment ENV    Set environment (development|production) [default: production]"
            echo "  -s, --scale N           Number of compute nodes to start [default: 2]"
            echo "  -h, --help              Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Set environment file
ENV_FILE=".env.${ENVIRONMENT}"
if [[ ! -f "$ENV_FILE" ]]; then
    print_error "Environment file $ENV_FILE not found"
    exit 1
fi

print_status "Using environment: $ENVIRONMENT"
print_status "Scaling compute nodes to: $SCALE_COMPUTE_NODES"

# Copy environment file
cp "$ENV_FILE" .env

# Start infrastructure services first
print_status "Starting infrastructure services..."
docker-compose up -d postgres rabbitmq redis

# Wait for infrastructure to be ready
print_status "Waiting for infrastructure services to be ready..."
sleep 10

# Start master node
print_status "Starting master node..."
docker-compose up -d master-node

# Wait for master node to be ready
print_status "Waiting for master node to be ready..."
sleep 5

# Start compute nodes
print_status "Starting compute nodes..."
docker-compose up -d --scale compute-node-1=$SCALE_COMPUTE_NODES compute-node-1

# Start frontend
print_status "Starting frontend..."
docker-compose up -d frontend

# Start monitoring (optional)
print_status "Starting monitoring services..."
docker-compose up -d prometheus grafana

print_status "All services started successfully! 🎉"
print_info ""
print_info "Services are now running:"
print_info "📊 Frontend:           http://localhost"
print_info "🔌 API:                http://localhost:8000"
print_info "📈 Prometheus:         http://localhost:9090"
print_info "📊 Grafana:            http://localhost:3000 (admin/admin)"
print_info "🐰 RabbitMQ:           http://localhost:15672 (gto_user/gto_password)"
print_info ""
print_info "Use 'docker-compose logs -f [service-name]' to view logs"
print_info "Use './scripts/stop.sh' to stop all services"
