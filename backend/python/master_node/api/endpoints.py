from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime
from ..services.simulation_manager import SimulationManager
from ..services.task_queue import TaskQueue

router = APIRouter()


# Modèles Pydantic pour l'API
class SimulationRequest(BaseModel):
    simulation_type: str  # "preflop" ou "postflop"
    game_config: Dict[str, Any]
    solver_config: Dict[str, Any]
    name: Optional[str] = None
    description: Optional[str] = None


class SimulationResponse(BaseModel):
    simulation_id: str
    status: str
    created_at: datetime
    estimated_completion_time: Optional[datetime] = None


class SimulationStatus(BaseModel):
    simulation_id: str
    status: str
    progress_percentage: float
    iterations_completed: int
    current_exploitability: Optional[float] = None
    estimated_time_remaining: Optional[int] = None  # en secondes


class SimulationResult(BaseModel):
    simulation_id: str
    final_strategy: Dict[str, Any]
    final_exploitability: float
    iterations_completed: int
    convergence_time: float
    metadata: Dict[str, Any]


# Initialisation des services
simulation_manager = SimulationManager()
task_queue = TaskQueue()


@router.get("/status")
async def get_status():
    """Statut général du nœud maître."""
    return {
        "status": "Nœud Maître opérationnel",
        "timestamp": datetime.now().isoformat(),
        "active_simulations": len(simulation_manager.get_active_simulations()),
        "queue_status": await task_queue.get_queue_status(),
    }


@router.post(
    "/simulations",
    status_code=201,
    response_model=SimulationResponse
)
async def create_simulation(
    simulation_request: SimulationRequest,
    background_tasks: BackgroundTasks
):
    """Créer et démarrer une nouvelle simulation."""
    try:
        # Générer un ID unique pour la simulation
        simulation_id = str(uuid.uuid4())

        # Valider les paramètres
        if simulation_request.simulation_type not in ["preflop", "postflop"]:
            raise HTTPException(
                status_code=400,
                detail="Type de simulation doit être 'preflop' ou 'postflop'",
            )

        # Créer la simulation
        simulation = await simulation_manager.create_simulation(
            simulation_id=simulation_id,
            simulation_type=simulation_request.simulation_type,
            game_config=simulation_request.game_config,
            solver_config=simulation_request.solver_config,
            name=simulation_request.name,
            description=simulation_request.description,
        )

        # Démarrer la simulation en arrière-plan
        background_tasks.add_task(simulation_manager.start_simulation, simulation_id)

        return SimulationResponse(
            simulation_id=simulation_id,
            status="started",
            created_at=simulation.created_at,
            estimated_completion_time=(
                simulation.estimated_completion_time
            ),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/simulations",
    response_model=List[SimulationResponse]
)
async def list_simulations(
    status: Optional[str] = None,
    simulation_type: Optional[str] = None,
    limit: int = 50
):
    """Lister les simulations."""
    try:
        simulations = await simulation_manager.list_simulations(
            status_filter=status, type_filter=simulation_type, limit=limit
        )

        return [
            SimulationResponse(
                simulation_id=sim.simulation_id,
                status=sim.status,
                created_at=sim.created_at,
                estimated_completion_time=(
                    sim.estimated_completion_time
                ),
            )
            for sim in simulations
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/simulations/{simulation_id}/status",
    response_model=SimulationStatus
)
async def get_simulation_status(simulation_id: str):
    """Obtenir le statut d'une simulation."""
    try:
        status = await simulation_manager.get_simulation_status(simulation_id)

        if not status:
            raise HTTPException(
                status_code=404, detail=f"Simulation {simulation_id} non trouvée"
            )

        return SimulationStatus(
            simulation_id=simulation_id,
            status=status.status,
            progress_percentage=status.progress_percentage,
            iterations_completed=status.iterations_completed,
            current_exploitability=(
                status.current_exploitability
            ),
            estimated_time_remaining=(
                status.estimated_time_remaining
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/simulations/{simulation_id}/results",
    response_model=SimulationResult
)
async def get_simulation_results(simulation_id: str):
    """Obtenir les résultats d'une simulation terminée."""
    try:
        results = await simulation_manager.get_simulation_results(simulation_id)

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Résultats pour la simulation {simulation_id} non trouvés",
            )

        return SimulationResult(
            simulation_id=simulation_id,
            final_strategy=results.final_strategy,
            final_exploitability=results.final_exploitability,
            iterations_completed=results.iterations_completed,
            convergence_time=results.convergence_time,
            metadata=results.metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/simulations/{simulation_id}")
async def cancel_simulation(simulation_id: str):
    """Annuler une simulation en cours."""
    try:
        success = await simulation_manager.cancel_simulation(simulation_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Simulation {simulation_id} non trouvée ou déjà terminée",
            )

        return {"message": f"Simulation {simulation_id} annulée"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compute-nodes")
async def list_compute_nodes():
    """Lister les nœuds de calcul disponibles."""
    try:
        nodes = await simulation_manager.get_compute_nodes_status()
        return {"compute_nodes": nodes}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/status")
async def get_queue_status():
    """Statut des files de messages."""
    try:
        status = await task_queue.get_detailed_queue_status()
        return status

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
