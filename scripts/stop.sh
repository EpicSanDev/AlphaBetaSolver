#!/bin/bash
# Stop script for GTO Poker Solver

set -e

echo "🛑 Stopping GTO Poker Solver..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Parse command line arguments
REMOVE_VOLUMES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --remove-volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --remove-volumes    Remove all volumes (WARNING: This will delete all data!)"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Stop all services
print_status "Stopping all services..."
docker-compose down

if [[ "$REMOVE_VOLUMES" == "true" ]]; then
    print_warning "Removing all volumes (this will delete all data)..."
    docker-compose down -v
    print_warning "All data has been removed!"
fi

print_status "All services stopped successfully! 🏁"

# Show status
if docker ps -q --filter "name=gto-" | grep -q .; then
    print_warning "Some containers are still running:"
    docker ps --filter "name=gto-"
else
    print_status "All GTO Solver containers have been stopped"
fi
