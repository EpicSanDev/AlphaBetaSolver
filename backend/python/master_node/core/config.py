import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Poker GTO Solver - Master Node"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # RabbitMQ Configuration
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_QUEUE_PREFLOP: str = "preflop_tasks"
    RABBITMQ_QUEUE_POSTFLOP: str = "postflop_tasks"

    # Database Configuration
    DATABASE_URL: str = "postgresql://gto_user:gto_password@localhost:5432/gto_solver"

    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"

    # Storage Configuration
    SIMULATION_STORAGE_PATH: str = "/tmp/gto_simulations"

    # C++ Solver Configuration
    POKER_SOLVER_BIN: str = "/app/bin/PokerSolver"

    # Monitoring Configuration
    PROMETHEUS_PORT: int = 8001
    ENABLE_METRICS: bool = True

    # Node Configuration
    NODE_TYPE: str = "master"
    NODE_ID: str = "master-node-1"
    MAX_CONCURRENT_TASKS: int = 10

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Security Configuration
    SECRET_KEY: str = "your-secret-key-change-in-production"
    API_KEYS: str = ""  # Comma-separated list of valid API keys
    ENABLE_AUTH: bool = False  # Set to True in production
    
    # Performance Configuration
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    CACHE_TTL: int = 300  # Cache TTL in seconds

    class Config:
        # Use .env.local if it exists, otherwise fall back to .env
        env_file = ".env.local" if os.path.exists(".env.local") else ".env"
        env_file_encoding = 'utf-8'

settings = Settings()