#!/bin/bash
# Build script for GTO Poker Solver

set -e

echo "🏗️  Building GTO Poker Solver..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose is not installed. Please install docker-compose first."
    exit 1
fi

# Check for required dependencies
print_status "Checking for required dependencies..."

# Check if Homebrew is installed
if ! command -v brew &> /dev/null; then
    print_warning "Homebrew is not installed. Attempting to install Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Check if Homebrew installation was successful
    if ! command -v brew &> /dev/null; then
        print_error "Failed to install Homebrew. Please install it manually and try again."
        exit 1
    fi
fi

# Install jsoncpp if not already installed
if ! brew list jsoncpp &> /dev/null; then
    print_status "Installing jsoncpp dependency..."
    brew install jsoncpp
    
    if [ $? -ne 0 ]; then
        print_error "Failed to install jsoncpp. Please install it manually and try again."
        exit 1
    else
        print_status "jsoncpp installed successfully"
    fi
else
    print_status "jsoncpp is already installed"
fi

# Build C++ components first
print_status "Building C++ solver..."
# Save current directory
ORIGINAL_DIR=$(pwd)
cd "$(dirname "$0")/.."  # Navigate to project root directory
PROJECT_ROOT=$(pwd)
cd backend
mkdir -p build
cd build

# Use Homebrew-installed jsoncpp
JSONCPP_PREFIX=$(brew --prefix jsoncpp)
print_status "Using jsoncpp from: $JSONCPP_PREFIX"

# Configure with jsoncpp path
cmake -DCMAKE_PREFIX_PATH=$JSONCPP_PREFIX ..
make

# Return to the project root directory
cd "$PROJECT_ROOT"

print_status "C++ solver built successfully"

# Build Docker images
print_status "Building Docker images..."

# Ensure we're in the project root directory
cd "$(dirname "$0")/.." 2>/dev/null || true

# Build backend image
print_status "Building backend image..."
docker build -f Dockerfile.backend -t gto-solver-backend .

# Build frontend image
print_status "Building frontend image..."
docker build -f Dockerfile.frontend -t gto-solver-frontend .

print_status "Docker images built successfully"

# Create data directories
print_status "Creating data directories..."
mkdir -p data logs

print_status "Build completed successfully! 🎉"
print_status "Run './scripts/start.sh' to start the services"
