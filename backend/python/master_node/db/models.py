from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Float,
    Integer,
    JSON,
    ForeignKey,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from master_node.db.database import Base


class Simulation(Base):
    __tablename__ = "simulations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255))
    description = Column(Text)
    simulation_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    game_config = Column(JSON, nullable=False)
    solver_config = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    progress = Column(Float, default=0.0)
    current_iteration = Column(Integer, default=0)
    total_iterations = Column(Integer)
    exploitability = Column(Float)

    # Relationships
    tasks = relationship(
        "Task", back_populates="simulation", cascade="all, delete-orphan"
    )
    results = relationship(
        "SimulationResult", back_populates="simulation", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_id = Column(
        UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=False
    )
    task_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    assigned_node_id = Column(String(255))
    task_data = Column(JSON, nullable=False)
    result_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # Relationships
    simulation = relationship("Simulation", back_populates="tasks")


class ComputeNode(Base):
    __tablename__ = "compute_nodes"

    id = Column(String(255), primary_key=True)
    status = Column(String(50), nullable=False, default="active")
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now())
    capacity = Column(Integer, nullable=False, default=4)
    current_tasks = Column(Integer, default=0)
    total_tasks_completed = Column(Integer, default=0)
    node_metadata = Column(
        JSON
    )  # Renamed from 'metadata' which is reserved in SQLAlchemy
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    simulation_id = Column(
        UUID(as_uuid=True), ForeignKey("simulations.id"), nullable=False
    )
    result_type = Column(
        String(50), nullable=False
    )  # 'strategy', 'exploitability', 'tree'
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    simulation = relationship("Simulation", back_populates="results")


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    labels = Column(JSON)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    simulation_id = Column(UUID(as_uuid=True), ForeignKey("simulations.id"))
    node_id = Column(String(255))


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    permissions = Column(ARRAY(String), default=[])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    key = Column(String(255), unique=True, nullable=False)
    permissions = Column(ARRAY(String), default=[])
    is_active = Column(Boolean, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used = Column(DateTime(timezone=True))
