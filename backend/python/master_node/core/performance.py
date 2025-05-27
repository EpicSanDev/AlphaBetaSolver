"""
Performance optimization utilities for the GTO Poker Solver.
Implements connection pooling, caching, and query optimization.
"""

import asyncio
import json
import time
from typing import Any, Optional, Dict, Callable
import redis
import logging
from functools import wraps
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import QueuePool

from .config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis-based caching manager."""

    def __init__(self):
        if settings.REDIS_URL:
            self.redis_client = redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
        else:
            self.redis_client = None
            logger.warning("Redis not configured, caching disabled")

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if not self.redis_client:
            return None

        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Cache get error: {e}")

        return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set a value in cache."""
        if not self.redis_client:
            return False

        try:
            ttl = ttl or settings.CACHE_TTL
            self.redis_client.setex(key, ttl, json.dumps(value, default=str))
            return True
        except (redis.RedisError, json.JSONEncodeError) as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if not self.redis_client:
            return False

        try:
            self.redis_client.delete(key)
            return True
        except redis.RedisError as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.exists(key))
        except redis.RedisError as e:
            logger.error(f"Cache exists error: {e}")
            return False


cache_manager = CacheManager()


def cache_result(key_prefix: str, ttl: int = None):
    """Decorator to cache function results."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cache miss for {cache_key}, result cached")

            return result

        return wrapper

    return decorator


class DatabaseManager:
    """Enhanced database manager with connection pooling."""

    def __init__(self):
        # Create engine with connection pooling
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            poolclass=QueuePool,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,  # Recycle connections every hour
            echo=settings.LOG_LEVEL == "DEBUG",
        )

        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def get_session(self):
        """Get a database session."""
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        """Close the database engine."""
        await self.engine.dispose()


db_manager = DatabaseManager()


class PerformanceMonitor:
    """Monitor and log performance metrics."""

    def __init__(self):
        self.metrics = {}

    def time_function(self, func_name: str):
        """Decorator to time function execution."""

        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self.record_timing(func_name, duration)

            return wrapper

        return decorator

    def record_timing(self, operation: str, duration: float):
        """Record timing for an operation."""
        if operation not in self.metrics:
            self.metrics[operation] = []

        self.metrics[operation].append(duration)

        # Keep only last 100 measurements
        if len(self.metrics[operation]) > 100:
            self.metrics[operation] = self.metrics[operation][-100:]

        # Log slow operations
        if duration > 1.0:  # Slower than 1 second
            logger.warning(f"Slow operation {operation}: {duration:.2f}s")

    def get_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for an operation."""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}

        timings = self.metrics[operation]
        return {
            "count": len(timings),
            "avg": sum(timings) / len(timings),
            "min": min(timings),
            "max": max(timings),
            "p95": sorted(timings)[int(len(timings) * 0.95)] if len(timings) > 0 else 0,
        }

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all operations."""
        return {op: self.get_stats(op) for op in self.metrics.keys()}


performance_monitor = PerformanceMonitor()


class QueryOptimizer:
    """Database query optimization utilities."""

    @staticmethod
    def build_filters(query, model, filters: Dict[str, Any]):
        """Build query filters dynamically."""
        for field, value in filters.items():
            if hasattr(model, field) and value is not None:
                if isinstance(value, list):
                    query = query.filter(getattr(model, field).in_(value))
                elif isinstance(value, dict) and "gte" in value:
                    query = query.filter(getattr(model, field) >= value["gte"])
                elif isinstance(value, dict) and "lte" in value:
                    query = query.filter(getattr(model, field) <= value["lte"])
                else:
                    query = query.filter(getattr(model, field) == value)
        return query

    @staticmethod
    def apply_pagination(query, page: int = 1, per_page: int = 20):
        """Apply pagination to query."""
        offset = (page - 1) * per_page
        return query.offset(offset).limit(per_page)


class BatchProcessor:
    """Process operations in batches for better performance."""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size

    async def process_batch(self, items: list, processor: Callable):
        """Process items in batches."""
        results = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            batch_results = await processor(batch)
            results.extend(batch_results)

            # Small delay to prevent overwhelming the system
            if i + self.batch_size < len(items):
                await asyncio.sleep(0.01)

        return results


batch_processor = BatchProcessor()
