"""
Advanced monitoring and alerting for the GTO Poker Solver.
Implements custom metrics, health checks, and alert rules.
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    start_http_server,
    CollectorRegistry,
    generate_latest,
)
import psutil
import aioredis
from sqlalchemy import text
from datetime import datetime

from .config import settings
from .database import get_db_session

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    name: str
    severity: AlertSeverity
    message: str
    timestamp: datetime
    labels: Dict[str, str] = None


class MetricsCollector:
    """Collect and expose custom metrics for the GTO Poker Solver."""

    def __init__(self):
        self.registry = CollectorRegistry()

        # API Metrics
        self.api_requests_total = Counter(
            "gto_api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status"],
            registry=self.registry,
        )

        self.api_request_duration = Histogram(
            "gto_api_request_duration_seconds",
            "API request duration",
            ["method", "endpoint"],
            registry=self.registry,
        )

        # Simulation Metrics
        self.simulations_total = Counter(
            "gto_simulations_total",
            "Total simulations created",
            ["status"],
            registry=self.registry,
        )

        self.simulation_duration = Histogram(
            "gto_simulation_duration_seconds",
            "Simulation duration",
            ["status"],
            registry=self.registry,
        )

        self.active_simulations = Gauge(
            "gto_active_simulations",
            "Number of active simulations",
            registry=self.registry,
        )

        # Compute Node Metrics
        self.compute_nodes_total = Gauge(
            "gto_compute_nodes_total", "Total compute nodes", registry=self.registry
        )

        self.compute_node_tasks = Gauge(
            "gto_compute_node_tasks",
            "Tasks per compute node",
            ["node_id", "status"],
            registry=self.registry,
        )

        # Queue Metrics
        self.queue_size = Gauge(
            "gto_queue_size", "Queue size", ["queue_name"], registry=self.registry
        )

        self.queue_processing_time = Histogram(
            "gto_queue_processing_time_seconds",
            "Queue message processing time",
            ["queue_name"],
            registry=self.registry
        )

        # System Metrics
        self.system_cpu_usage = Gauge(
            "gto_system_cpu_usage_percent", "System CPU usage", registry=self.registry
        )

        self.system_memory_usage = Gauge(
            "gto_system_memory_usage_percent",
            "System memory usage",
            registry=self.registry,
        )

        self.system_disk_usage = Gauge(
            "gto_system_disk_usage_percent",
            "System disk usage",
            ["mount_point"],
            registry=self.registry
        )

        # Database Metrics
        self.db_connections = Gauge(
            "gto_db_connections",
            "Database connections",
            ["state"],
            registry=self.registry,
        )

        self.db_query_duration = Histogram(
            "gto_db_query_duration_seconds",
            "Database query duration",
            ["query_type"],
            registry=self.registry,
        )

        # Cache Metrics
        self.cache_hits = Counter(
            "gto_cache_hits_total", "Cache hits", registry=self.registry
        )

        self.cache_misses = Counter(
            "gto_cache_misses_total", "Cache misses", registry=self.registry
        )

        # Application Info
        self.app_info = Info(
            "gto_app_info", "Application information", registry=self.registry
        )

        # Set application info
        self.app_info.info(
            {
                "version": getattr(settings, "VERSION", "1.0.0"),
                "environment": getattr(settings, "ENVIRONMENT", "development"),
                "build_time": getattr(settings, "BUILD_TIME", str(datetime.now())),
            }
        )

    def record_api_request(
        self, method: str, endpoint: str, status: int, duration: float
    ):
        """Record API request metrics."""
        self.api_requests_total.labels(
            method=method, endpoint=endpoint, status=status
        ).inc()
        self.api_request_duration.labels(method=method, endpoint=endpoint).observe(
            duration
        )

    def record_simulation(self, status: str, duration: Optional[float] = None):
        """Record simulation metrics."""
        self.simulations_total.labels(status=status).inc()
        if duration is not None:
            self.simulation_duration.labels(status=status).observe(duration)

    def update_active_simulations(self, count: int):
        """Update active simulations count."""
        self.active_simulations.set(count)

    def update_compute_nodes(self, total: int):
        """Update total compute nodes count."""
        self.compute_nodes_total.set(total)

    def update_compute_node_tasks(self, node_id: str, status: str, count: int):
        """Update compute node task metrics."""
        self.compute_node_tasks.labels(node_id=node_id, status=status).set(count)

    def update_queue_metrics(self, queue_name: str, size: int):
        """Update queue size metrics."""
        self.queue_size.labels(queue_name=queue_name).set(size)

    def record_queue_processing(self, queue_name: str, duration: float):
        """Record queue processing time."""
        self.queue_processing_time.labels(queue_name=queue_name).observe(duration)

    def record_cache_hit(self):
        """Record cache hit."""
        self.cache_hits.inc()

    def record_cache_miss(self):
        """Record cache miss."""
        self.cache_misses.inc()

    def record_db_query(self, query_type: str, duration: float):
        """Record database query metrics."""
        self.db_query_duration.labels(query_type=query_type).observe(duration)

    async def collect_system_metrics(self):
        """Collect system metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.system_cpu_usage.set(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            self.system_memory_usage.set(memory.percent)

            # Disk usage
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    self.system_disk_usage.labels(mount_point=partition.mountpoint).set(
                        (usage.used / usage.total) * 100
                    )
                except PermissionError:
                    continue

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

    async def collect_database_metrics(self):
        """Collect database metrics."""
        try:
            async with get_db_session() as session:
                # Get connection count
                result = await session.execute(
                    text("SELECT state, count(*) FROM pg_stat_activity GROUP BY state")
                )

                for state, count in result:
                    self.db_connections.labels(state=state or "unknown").set(count)

        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")

    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry).decode("utf-8")


class HealthChecker:
    """Health check system for all components."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.checks = {}
        self.last_check = {}

    def register_check(self, name: str, check_func, interval: int = 30):
        """Register a health check."""
        self.checks[name] = {
            "func": check_func,
            "interval": interval,
            "status": "unknown",
            "last_success": None,
            "last_error": None,
        }

    async def run_check(self, name: str) -> Dict[str, Any]:
        """Run a specific health check."""
        check = self.checks[name]

        try:
            start_time = time.time()
            result = await check["func"]()
            duration = time.time() - start_time

            check["status"] = "healthy"
            check["last_success"] = datetime.now()
            check["duration"] = duration

            return {
                "name": name,
                "status": "healthy",
                "duration": duration,
                "result": result,
            }

        except Exception as e:
            check["status"] = "unhealthy"
            check["last_error"] = str(e)

            logger.error(f"Health check {name} failed: {e}")

            return {"name": name, "status": "unhealthy", "error": str(e)}

    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}

        for name in self.checks:
            results[name] = await self.run_check(name)

        # Overall health status
        overall_status = "healthy"
        for result in results.values():
            if result["status"] == "unhealthy":
                overall_status = "unhealthy"
                break

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "checks": results,
        }


class AlertManager:
    """Manage alerts and notifications."""

    def __init__(self):
        self.alerts = []
        self.alert_rules = []

    def add_rule(self, name: str, condition, message: str, severity: AlertSeverity):
        """Add an alert rule."""
        self.alert_rules.append(
            {
                "name": name,
                "condition": condition,
                "message": message,
                "severity": severity,
            }
        )

    def check_rules(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check all alert rules against current metrics."""
        triggered_alerts = []

        for rule in self.alert_rules:
            try:
                if rule["condition"](metrics):
                    alert = Alert(
                        name=rule["name"],
                        severity=rule["severity"],
                        message=rule["message"],
                        timestamp=datetime.now(),
                    )
                    triggered_alerts.append(alert)
            except Exception as e:
                logger.error(f"Error checking alert rule {rule['name']}: {e}")

        return triggered_alerts

    async def send_alert(self, alert: Alert):
        """Send an alert notification."""
        logger.warning(
            f"ALERT [{alert.severity.value.upper()}] {alert.name}: {alert.message}"
        )

        # Here you could integrate with external alerting systems:
        # - Slack
        # - PagerDuty
        # - Email
        # - Discord
        # etc.


class MonitoringService:
    """Main monitoring service that coordinates all monitoring components."""

    def __init__(self):
        self.metrics = MetricsCollector()
        self.health_checker = HealthChecker(self.metrics)
        self.alert_manager = AlertManager()
        self.running = False

        # Register health checks
        self._setup_health_checks()

        # Setup alert rules
        self._setup_alert_rules()

    def _setup_health_checks(self):
        """Setup default health checks."""

        async def database_check():
            async with get_db_session() as session:
                await session.execute(text("SELECT 1"))
            return "Database connection OK"

        async def redis_check():
            if settings.REDIS_URL:
                redis = aioredis.from_url(settings.REDIS_URL)
                await redis.ping()
                await redis.close()
                return "Redis connection OK"
            return "Redis not configured"

        async def disk_space_check():
            usage = psutil.disk_usage("/")
            free_percent = (usage.free / usage.total) * 100
            if free_percent < 10:
                raise Exception(f"Low disk space: {free_percent:.1f}% free")
            return f"Disk space OK: {free_percent:.1f}% free"

        self.health_checker.register_check("database", database_check, 30)
        self.health_checker.register_check("redis", redis_check, 30)
        self.health_checker.register_check("disk_space", disk_space_check, 60)

    def _setup_alert_rules(self):
        """Setup default alert rules."""

        # High error rate
        self.alert_manager.add_rule(
            "high_error_rate",
            lambda m: m.get("error_rate", 0) > 0.05,
            "Error rate is above 5%",
            AlertSeverity.WARNING,
        )

        # High response time
        self.alert_manager.add_rule(
            "high_response_time",
            lambda m: m.get("avg_response_time", 0) > 1.0,
            "Average response time is above 1 second",
            AlertSeverity.WARNING,
        )

        # High CPU usage
        self.alert_manager.add_rule(
            "high_cpu_usage",
            lambda m: m.get("cpu_usage", 0) > 80,
            "CPU usage is above 80%",
            AlertSeverity.CRITICAL,
        )

        # High memory usage
        self.alert_manager.add_rule(
            "high_memory_usage",
            lambda m: m.get("memory_usage", 0) > 90,
            "Memory usage is above 90%",
            AlertSeverity.CRITICAL,
        )

    async def start(self, port: int = 8001):
        """Start the monitoring service."""
        self.running = True

        # Start Prometheus metrics server
        start_http_server(port, registry=self.metrics.registry)
        logger.info(f"Metrics server started on port {port}")

        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())

    async def stop(self):
        """Stop the monitoring service."""
        self.running = False

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Collect system metrics
                await self.metrics.collect_system_metrics()

                # Collect database metrics
                await self.metrics.collect_database_metrics()

                # Run health checks
                health_results = await self.health_checker.run_all_checks()

                # Check alert rules
                current_metrics = {
                    "cpu_usage": psutil.cpu_percent(),
                    "memory_usage": psutil.virtual_memory().percent,
                    # Add more metrics as needed
                }

                alerts = self.alert_manager.check_rules(current_metrics)
                for alert in alerts:
                    await self.alert_manager.send_alert(alert)

                # Sleep before next iteration
                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)


# Global monitoring service instance
monitoring_service = MonitoringService()


# Utility functions for easy access
def record_api_request(method: str, endpoint: str, status: int, duration: float):
    """Record API request metrics."""
    monitoring_service.metrics.record_api_request(method, endpoint, status, duration)


def record_simulation(status: str, duration: Optional[float] = None):
    """Record simulation metrics."""
    monitoring_service.metrics.record_simulation(status, duration)


def record_cache_hit():
    """Record cache hit."""
    monitoring_service.metrics.record_cache_hit()


def record_cache_miss():
    """Record cache miss."""
    monitoring_service.metrics.record_cache_miss()
