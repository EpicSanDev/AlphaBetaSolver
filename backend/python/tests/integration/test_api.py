import pytest
from unittest.mock import AsyncMock, patch

class TestAPI:
    """Test API endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Welcome" in response.json()["message"]
    
    @patch('master_node.services.simulation_manager.SimulationManager')
    def test_create_simulation(self, mock_simulation_manager, client):
        """Test creating a simulation."""
        mock_manager = AsyncMock()
        mock_simulation_manager.return_value = mock_manager
        mock_manager.create_simulation.return_value = {
            "simulation_id": "test-id",
            "status": "pending"
        }
        
        simulation_data = {
            "simulation_type": "preflop",
            "name": "Test Simulation",
            "description": "Test description",
            "game_config": {
                "stack_size": 100,
                "small_blind": 0.5,
                "big_blind": 1.0
            },
            "solver_config": {
                "max_iterations": 1000,
                "target_exploitability": 0.5
            }
        }
        
        response = client.post("/api/v1/simulations", json=simulation_data)
        assert response.status_code == 200
        assert "simulation_id" in response.json()
    
    def test_create_simulation_invalid_data(self, client):
        """Test creating a simulation with invalid data."""
        invalid_data = {
            "simulation_type": "invalid_type"
            # Missing required fields
        }
        
        response = client.post("/api/v1/simulations", json=invalid_data)
        assert response.status_code == 422  # Validation error

class TestSimulationEndpoints:
    """Test simulation-specific endpoints."""
    
    @patch('master_node.services.simulation_manager.SimulationManager')
    def test_get_simulation_status(self, mock_simulation_manager, client):
        """Test getting simulation status."""
        mock_manager = AsyncMock()
        mock_simulation_manager.return_value = mock_manager
        mock_manager.get_simulation_status.return_value = {
            "simulation_id": "test-id",
            "status": "running",
            "progress": 0.5,
            "current_iteration": 500,
            "total_iterations": 1000
        }
        
        response = client.get("/api/v1/simulations/test-id/status")
        assert response.status_code == 200
        assert response.json()["status"] == "running"
    
    def test_get_nonexistent_simulation(self, client):
        """Test getting status of non-existent simulation."""
        response = client.get("/api/v1/simulations/nonexistent-id/status")
        assert response.status_code == 404
