#!/bin/bash
# Development setup script for GTO Poker Solver

set -e

echo "🛠️  Setting up GTO Poker Solver development environment..."

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

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    # Check CMake
    if ! command -v cmake &> /dev/null; then
        print_error "CMake is not installed"
        exit 1
    fi
    
    # Check pkg-config
    if ! command -v pkg-config &> /dev/null; then
        print_warning "pkg-config is not installed (may be needed for jsoncpp)"
    fi
    
    print_status "Prerequisites check completed"
}

# Setup Python virtual environment
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    cd backend/python
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies
    pip install -r requirements.txt
    
    print_status "Python environment setup completed"
    cd ../..
}

# Build C++ components
build_cpp() {
    print_status "Building C++ components..."
    
    cd backend
    mkdir -p build
    cd build
    
    # Configure and build
    cmake ..
    make
    
    print_status "C++ build completed"
    cd ../..
}

# Setup development databases
setup_dev_db() {
    print_status "Setting up development databases..."
    
    # Check if PostgreSQL is running
    if ! pg_isready -h localhost -p 5432 &> /dev/null; then
        print_warning "PostgreSQL is not running. Starting with Docker..."
        docker run -d \
            --name gto-postgres-dev \
            -e POSTGRES_DB=gto_solver \
            -e POSTGRES_USER=gto_user \
            -e POSTGRES_PASSWORD=gto_password \
            -p 5432:5432 \
            postgres:15-alpine
        
        print_status "Waiting for PostgreSQL to be ready..."
        sleep 10
    fi
    
    # Check if RabbitMQ is running
    if ! curl -s http://localhost:15672 &> /dev/null; then
        print_warning "RabbitMQ is not running. Starting with Docker..."
        docker run -d \
            --name gto-rabbitmq-dev \
            -e RABBITMQ_DEFAULT_USER=gto_user \
            -e RABBITMQ_DEFAULT_PASS=gto_password \
            -p 5672:5672 \
            -p 15672:15672 \
            rabbitmq:3-management-alpine
        
        print_status "Waiting for RabbitMQ to be ready..."
        sleep 15
    fi
    
    print_status "Development databases setup completed"
}

# Run tests
run_tests() {
    print_status "Running tests..."
    
    cd backend/python
    source venv/bin/activate
    
    # Run pytest
    pytest tests/ -v
    
    print_status "Tests completed"
    cd ../..
}

# Main execution
check_prerequisites
setup_python_env
build_cpp
setup_dev_db

print_status "Development environment setup completed! 🎉"
print_info ""
print_info "To start development:"
print_info "1. Activate Python environment: cd backend/python && source venv/bin/activate"
print_info "2. Start master node: python -m master_node.main"
print_info "3. Start compute node: python -m compute_node.agent"
print_info ""
print_info "Development services:"
print_info "🗄️  PostgreSQL:        localhost:5432"
print_info "🐰 RabbitMQ:           localhost:15672"
print_info ""
print_info "Use 'docker ps' to see running containers"
print_info "Use './scripts/build.sh' to build for production"
