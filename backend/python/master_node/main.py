import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_client import start_http_server
import os

from master_node.core.config import settings
from master_node.db import init_db, close_db
from master_node.services.task_queue import TaskQueue
from master_node.services.simulation_manager import SimulationManager
from master_node.services.compute_node_manager import get_compute_node_manager
from master_node.api import endpoints
from master_node.api.websocket import websocket_endpoint

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL), format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Global services
task_queue = None
simulation_manager = None
compute_node_manager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global task_queue, simulation_manager, compute_node_manager

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

        # Initialize compute node manager
        compute_node_manager = get_compute_node_manager()
        logger.info("Compute node manager initialized")

        # Initialize simulation manager
        simulation_manager = SimulationManager(
            task_queue,
            settings.SIMULATION_STORAGE_PATH
        )
        await simulation_manager.start()
        logger.info("Simulation manager started")

        # Make services available to endpoints
        app.state.compute_node_manager = compute_node_manager
        app.state.simulation_manager = simulation_manager
        app.state.task_queue = task_queue

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

        if compute_node_manager:
            await compute_node_manager.cleanup()

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


@app.get("/download/compute_client.py")
async def download_compute_client():
    """Serve the compute client file for download"""
    client_path = "/app/compute_client.py"  # Path in Docker container
    if os.path.exists(client_path):
        return FileResponse(
            path=client_path,
            filename="compute_client.py",
            media_type="text/x-python"
        )
    else:
        return {"error": "Compute client file not found"}


app.include_router(endpoints.router, prefix=settings.API_V1_STR)

# WebSocket endpoint for real-time monitoring (no authentication required)
@app.websocket("/ws")
async def websocket_monitoring(websocket: WebSocket):
    """WebSocket endpoint for real-time monitoring. No authentication required."""
    client_addr = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "Unknown client"
    try:
        await websocket.accept()
        logger.info(f"WebSocket connection established with {client_addr}")
        await websocket.send_text("Connection established")
        
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received data from {client_addr}: {data}")
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_addr} disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error with {client_addr}: {e}")
        # Starlette/Uvicorn should handle closing the WebSocket connection
        # in case of unhandled exceptions. Explicitly calling websocket.close() here
        # can lead to RuntimeError if the socket is already being closed.


# Simple WebSocket test endpoint
@app.websocket("/ws-test")
async def websocket_test(websocket: WebSocket):
    """Simple WebSocket test endpoint"""
    await websocket.accept()
    await websocket.send_text("Hello WebSocket!")
    await websocket.close()


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


def main():
    """Main function to start the server"""
    import uvicorn

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Starting server on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    main()
