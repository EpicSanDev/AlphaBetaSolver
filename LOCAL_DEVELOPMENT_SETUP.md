# Local Development Setup Guide

## Problem Solved ✅

The RabbitMQ connection error you encountered was due to configuration mismatches when running the Python application locally while the infrastructure (RabbitMQ, PostgreSQL, Redis) runs in Docker containers.

## Root Cause

The error occurred because:
1. The application was configured to use Docker-internal hostnames (`rabbitmq`) when running locally
2. File system paths were hardcoded for Docker containers (`/app/storage/simulations`)
3. Configuration didn't differentiate between Docker and local development environments

## Solution Implemented

### 1. Created Local Environment Configuration

File: `/Users/bastienjavaux/Desktop/AlphaBetaSolver/backend/python/.env.local`

```env
# Local development environment configuration
# Use this when running Python code locally while databases run in Docker

# RabbitMQ Configuration (connect to Docker container)
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=gto_user
RABBITMQ_PASSWORD=gto_password

# Database Configuration (connect to Docker container)
DATABASE_URL=postgresql://gto_user:gto_password@localhost:5432/gto_solver

# Redis Configuration (connect to Docker container)
REDIS_URL=redis://localhost:6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8002

# Storage Configuration (local development paths)
SIMULATION_STORAGE_PATH=/tmp/gto_simulations

# C++ Solver Configuration (adjust path for local development)
POKER_SOLVER_BIN=/Users/bastienjavaux/Desktop/AlphaBetaSolver/backend/build/src/PokerSolver

# Node Configuration
NODE_TYPE=master
NODE_ID=master-node-local
MAX_CONCURRENT_TASKS=4

# Monitoring Configuration (avoid conflicts with Docker)
PROMETHEUS_PORT=8003

# Logging Configuration
LOG_LEVEL=DEBUG
```

### 2. Updated Configuration Loading

Modified `config.py` to automatically detect and use `.env.local` when available:

```python
class Config:
    # Use .env.local if it exists, otherwise fall back to .env
    env_file = ".env.local" if os.path.exists(".env.local") else ".env"
    env_file_encoding = 'utf-8'
```

### 3. Fixed Queue Status Method

Updated the `get_queue_status()` method in `TaskQueue` to properly handle aio-pika queue objects.

### 4. Added Storage Path Configuration

Added `SIMULATION_STORAGE_PATH` setting to make storage paths configurable.

## How to Use

### For Docker Development (Default)
```bash
# Start all services with Docker
docker-compose up -d

# Access services:
# - API: http://localhost:8000
# - RabbitMQ Management: http://localhost:15672 (gto_user/gto_password)
# - Grafana: http://localhost:3000
```

### For Local Python Development

1. **Start infrastructure services:**
   ```bash
   docker-compose up -d rabbitmq postgres redis
   ```

2. **Activate Python environment:**
   ```bash
   cd backend/python
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the application locally:**
   ```bash
   python -m master_node.main
   ```

4. **Access services:**
   - Local API: http://localhost:8002
   - RabbitMQ Management: http://localhost:15672
   - Prometheus: http://localhost:8003

## Verification Tests ✅

All tests passed successfully:

1. **RabbitMQ Connection**: ✅ Connected successfully with correct credentials
2. **Queue Operations**: ✅ Queue declaration and status retrieval working
3. **Task Queue**: ✅ Publishing tasks to correct queues
4. **Simulation Manager**: ✅ Creating and managing simulations
5. **API Endpoints**: ✅ All endpoints responding correctly
6. **Full Integration**: ✅ Created simulation with 10 tasks in queue

## Files Modified

1. `backend/python/.env.local` - Created local development configuration
2. `backend/python/master_node/core/config.py` - Updated config loading logic
3. `backend/python/master_node/services/task_queue.py` - Fixed queue status method
4. `backend/python/master_node/main.py` - Use configurable storage path

## Development Workflow

### Option 1: Full Docker (Recommended for production-like testing)
- Everything runs in Docker containers
- Consistent environment across developers
- Use this for final testing before deployment

### Option 2: Hybrid (Recommended for development)
- Infrastructure in Docker (RabbitMQ, PostgreSQL, Redis)
- Python code runs locally
- Faster development cycle with hot reloading
- Better debugging capabilities

### Option 3: Local Everything (Advanced)
- Install and run all services locally
- Most complex setup but maximum control
- Use this only if Docker is not available

## Key Benefits of This Solution

1. **Environment Flexibility**: Can run in Docker or locally without code changes
2. **Automatic Detection**: Automatically uses local config when available
3. **Port Conflict Avoidance**: Uses different ports for local development
4. **Proper Credentials**: Uses correct RabbitMQ credentials from Docker setup
5. **File System Compatibility**: Uses accessible paths for local development

## Next Steps

The RabbitMQ connection issue is completely resolved. You can now:

1. Continue developing with the hybrid setup (infrastructure in Docker, Python locally)
2. Add more endpoints and functionality
3. Test with actual compute nodes
4. Deploy to production when ready

The system is fully functional and ready for continued development!
