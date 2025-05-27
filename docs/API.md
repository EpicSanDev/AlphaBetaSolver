# GTO Poker Solver API Documentation

## Overview

The GTO Poker Solver provides a REST API for managing poker game theory optimal (GTO) simulations. The API follows RESTful principles and returns JSON responses.

## Base URL

- Development: `http://localhost:8000`
- Production: Configure according to your deployment

## Authentication

Currently, the API does not require authentication. In production environments, implement proper authentication mechanisms.

## API Endpoints

### Health Check

Check if the API is running and healthy.

**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "service": "gto-solver-master"
}
```

### System Status

Get overall system status including queue and compute nodes.

**GET** `/api/v1/status`

**Response:**
```json
{
  "status": "running",
  "version": "1.0.0",
  "uptime": 3600,
  "active_simulations": 2,
  "compute_nodes": 3
}
```

### Simulations

#### Create Simulation

Create a new GTO simulation.

**POST** `/api/v1/simulations`

**Request Body:**
```json
{
  "simulation_type": "preflop",
  "name": "6-max NL100 Preflop",
  "description": "Preflop GTO analysis for 6-max NL100",
  "game_config": {
    "game_type": "nlhe",
    "max_players": 6,
    "stack_size": 100,
    "small_blind": 0.5,
    "big_blind": 1.0,
    "positions": ["BTN", "SB", "BB", "UTG", "MP", "CO"]
  },
  "solver_config": {
    "max_iterations": 1000,
    "target_exploitability": 0.5,
    "batch_size": 100,
    "use_chance_sampling": true,
    "use_discounting": false
  }
}
```

**Response:**
```json
{
  "simulation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Simulation created successfully"
}
```

#### Get Simulation Status

Get the current status of a simulation.

**GET** `/api/v1/simulations/{simulation_id}/status`

**Response:**
```json
{
  "simulation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": 45.2,
  "current_iteration": 452,
  "total_iterations": 1000,
  "current_exploitability": 1.2,
  "target_exploitability": 0.5,
  "estimated_completion": "2025-05-27T15:30:00Z",
  "runtime": 1800
}
```

#### Get Simulation Results

Get the results of a completed simulation.

**GET** `/api/v1/simulations/{simulation_id}/results`

**Response:**
```json
{
  "simulation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "final_exploitability": 0.45,
  "iterations_completed": 987,
  "runtime": 3600,
  "strategy": {
    "preflop": {
      "BTN": {
        "AA": {"fold": 0.0, "call": 0.0, "raise": 1.0},
        "KK": {"fold": 0.0, "call": 0.0, "raise": 1.0}
      }
    }
  }
}
```

#### List Simulations

Get a list of all simulations.

**GET** `/api/v1/simulations`

**Query Parameters:**
- `status` (optional): Filter by status (pending, running, completed, failed)
- `limit` (optional): Number of results per page (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "simulations": [
    {
      "simulation_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "6-max NL100 Preflop",
      "status": "completed",
      "created_at": "2025-05-27T12:00:00Z",
      "completed_at": "2025-05-27T13:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### Queue Management

#### Get Queue Status

Get the current status of the task queue.

**GET** `/api/v1/queue/status`

**Response:**
```json
{
  "preflop_tasks": 15,
  "postflop_tasks": 8,
  "pending_results": 3,
  "connected": true,
  "queue_health": "healthy"
}
```

### Compute Nodes

#### List Compute Nodes

Get information about all compute nodes.

**GET** `/api/v1/compute-nodes`

**Response:**
```json
{
  "compute_nodes": [
    {
      "node_id": "compute-node-1",
      "status": "active",
      "current_tasks": 2,
      "total_capacity": 4,
      "last_heartbeat": "2025-05-27T14:30:00Z",
      "total_tasks_completed": 156
    }
  ]
}
```

## Error Responses

The API returns standard HTTP status codes and error messages:

### 400 Bad Request
```json
{
  "error": "validation_error",
  "message": "Invalid request data",
  "details": {
    "field": "simulation_type",
    "issue": "must be one of: preflop, postflop, full_game"
  }
}
```

### 404 Not Found
```json
{
  "error": "not_found",
  "message": "Simulation not found",
  "simulation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 500 Internal Server Error
```json
{
  "error": "internal_error",
  "message": "An internal server error occurred",
  "request_id": "req_123456789"
}
```

## Rate Limiting

The API implements rate limiting to prevent abuse:

- **General endpoints**: 100 requests per minute
- **Simulation creation**: 10 requests per minute
- **Status endpoints**: 200 requests per minute

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: The rate limit ceiling
- `X-RateLimit-Remaining`: The number of requests left for the time window
- `X-RateLimit-Reset`: The time at which the rate limit window resets

## WebSocket Events

The API also supports WebSocket connections for real-time updates:

**WebSocket URL**: `ws://localhost:8000/ws/simulations/{simulation_id}`

**Events:**
- `progress_update`: Simulation progress updates
- `status_change`: Simulation status changes
- `error`: Error notifications

## SDK Examples

### Python
```python
import requests

# Create simulation
response = requests.post(
    "http://localhost:8000/api/v1/simulations",
    json={
        "simulation_type": "preflop",
        "name": "Test Simulation",
        "game_config": {"stack_size": 100},
        "solver_config": {"max_iterations": 1000}
    }
)
simulation_id = response.json()["simulation_id"]

# Check status
status = requests.get(f"http://localhost:8000/api/v1/simulations/{simulation_id}/status")
print(status.json())
```

### JavaScript
```javascript
// Create simulation
const response = await fetch('http://localhost:8000/api/v1/simulations', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    simulation_type: 'preflop',
    name: 'Test Simulation',
    game_config: { stack_size: 100 },
    solver_config: { max_iterations: 1000 }
  })
});
const { simulation_id } = await response.json();

// Check status
const status = await fetch(`http://localhost:8000/api/v1/simulations/${simulation_id}/status`);
console.log(await status.json());
```
