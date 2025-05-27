import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import start_http_server

from master_node.core.config import settings
from master_node.db import init_db, close_db
from master_node.services.task_queue import TaskQueue
from master_node.services.simulation_manager import SimulationManager
from master_node.api import endpoints

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL), format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Global services
task_queue = None
simulation_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global task_queue, simulation_manager

    logger.info("Starting GTO Poker Solver Master Node...")

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Start Prometheus metrics server if enabled
        if settings.ENABLE_METRICS:
            start_http_server(settings.PROMETHEUS_PORT)
            logger.info(
                f"Prometheus metrics server started on port {settings.PROMETHEUS_PORT}"
            )

        # Initialize task queue
        task_queue = TaskQueue()
        await task_queue.connect()
        logger.info("Task queue connected")

        # Initialize simulation manager
        simulation_manager = SimulationManager(
            task_queue,
            settings.SIMULATION_STORAGE_PATH
        )
        await simulation_manager.start()
        logger.info("Simulation manager started")

        # Start background tasks
        asyncio.create_task(heartbeat_task())

        logger.info("Master node startup complete")
        yield

    except Exception as e:
        logger.error(f"Failed to start master node: {e}")
        sys.exit(1)

    finally:
        # Cleanup
        logger.info("Shutting down Master Node...")

        if simulation_manager:
            await simulation_manager.stop()

        if task_queue:
            await task_queue.close()

        await close_db()
        logger.info("Master node shutdown complete")


app = FastAPI(
    title="Poker GTO Solver - Master Node",
    description="API for managing simulations and resources of the GTO solver.",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "gto-solver-master"}


@app.get("/")
async def root():
    return {
        "message": "Welcome to the GTO Poker Solver Master Node API",
        "version": "1.0.0",
        "status": "running",
    }


app.include_router(endpoints.router, prefix=settings.API_V1_STR)


async def heartbeat_task():
    """Periodic heartbeat task"""
    while True:
        try:
            # Update node status in database
            logger.debug("Heartbeat - Master node is alive")
            await asyncio.sleep(30)  # Heartbeat every 30 seconds
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            await asyncio.sleep(30)


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    import uvicorn

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Starting server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "master_node.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        workers=1,
    )
