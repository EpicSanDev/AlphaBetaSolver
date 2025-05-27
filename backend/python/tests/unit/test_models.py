import pytest
from master_node.db.models import Simulation, Task, ComputeNode

class TestSimulationModel:
    """Test simulation database model."""
    
    @pytest.mark.asyncio
    async def test_create_simulation(self, db_session):
        """Test creating a simulation."""
        simulation_data = {
            "name": "Test Simulation",
            "description": "Test description",
            "simulation_type": "preflop",
            "game_config": {"stack_size": 100, "sb": 0.5, "bb": 1.0},
            "solver_config": {"max_iterations": 1000, "target_exploitability": 0.5}
        }
        
        simulation = Simulation(**simulation_data)
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)
        
        assert simulation.id is not None
        assert simulation.name == "Test Simulation"
        assert simulation.status == "pending"
        assert simulation.progress == 0.0

    @pytest.mark.asyncio
    async def test_simulation_task_relationship(self, db_session):
        """Test simulation-task relationship."""
        # Create simulation
        simulation = Simulation(
            name="Test Simulation",
            simulation_type="preflop",
            game_config={},
            solver_config={}
        )
        db_session.add(simulation)
        await db_session.commit()
        await db_session.refresh(simulation)
        
        # Create task
        task = Task(
            simulation_id=simulation.id,
            task_type="preflop",
            task_data={"board": []}
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)
        
        # Test relationship
        await db_session.refresh(simulation, ["tasks"])
        assert len(simulation.tasks) == 1
        assert simulation.tasks[0].id == task.id

class TestComputeNodeModel:
    """Test compute node database model."""
    
    @pytest.mark.asyncio
    async def test_create_compute_node(self, db_session):
        """Test creating a compute node."""
        node = ComputeNode(
            id="test-node-1",
            capacity=4,
            node_metadata={"version": "1.0.0"}
        )
        
        db_session.add(node)
        await db_session.commit()
        await db_session.refresh(node)
        
        assert node.id == "test-node-1"
        assert node.status == "active"
        assert node.capacity == 4
        assert node.current_tasks == 0
