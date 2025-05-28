from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime

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


class ComputeNodeRegistration(BaseModel):
    node_id: str
    platform: str
    architecture: str
    cpu_count: int
    memory_total: int
    max_concurrent_tasks: int
    python_version: Optional[str] = None


class ComputeNodeHeartbeat(BaseModel):
    current_tasks: int
    status: str  # available, busy
    cpu_usage: float
    memory_usage: float


class TaskResult(BaseModel):
    task_id: str
    node_id: str
    status: str  # completed, failed, cancelled
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.get("/status")
async def get_status(request: Request):
    """Statut général du nœud maître."""
    simulation_manager = request.app.state.simulation_manager
    task_queue = request.app.state.task_queue
    
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
    background_tasks: BackgroundTasks,
    request: Request
):
    """Créer et démarrer une nouvelle simulation."""
    simulation_manager = request.app.state.simulation_manager
    
    try:
        # Générer un ID unique pour la simulation
        simulation_id = str(uuid.uuid4())

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
        background_tasks.add_task(
            simulation_manager.start_simulation, simulation_id
        )

        return SimulationResponse(
            simulation_id=simulation.simulation_id,
            status=simulation.status.value,
            created_at=simulation.created_at,
            estimated_completion_time=simulation.estimated_completion_time,
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lors de la création de la simulation: {str(e)}")


@router.get("/simulations")
async def list_simulations(
    status: Optional[str] = None,
    simulation_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    request: Request = None
):
    """Lister toutes les simulations avec filtres optionnels."""
    simulation_manager = request.app.state.simulation_manager
    
    try:
        simulations = simulation_manager.get_all_simulations()

        # Appliquer les filtres
        if status:
            simulations = [s for s in simulations if s.status.value == status]
        if simulation_type:
            simulations = [s for s in simulations if s.simulation_type == simulation_type]

        # Pagination
        total = len(simulations)
        simulations = simulations[offset : offset + limit]

        return {
            "simulations": [
                {
                    "simulation_id": s.simulation_id,
                    "simulation_type": s.simulation_type,
                    "status": s.status.value,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "name": s.name,
                    "description": s.description,
                }
                for s in simulations
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des simulations: {str(e)}")


@router.get("/simulations/{simulation_id}/status", response_model=SimulationStatus)
async def get_simulation_status(simulation_id: str, request: Request):
    """Obtenir le statut détaillé d'une simulation."""
    simulation_manager = request.app.state.simulation_manager
    
    try:
        simulation = simulation_manager.get_simulation(simulation_id)
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation non trouvée")

        return SimulationStatus(
            simulation_id=simulation.simulation_id,
            status=simulation.status.value,
            progress_percentage=simulation.progress_percentage,
            iterations_completed=simulation.iterations_completed,
            current_exploitability=simulation.current_exploitability,
            estimated_time_remaining=simulation.estimated_time_remaining,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération du statut: {str(e)}")


@router.get("/simulations/{simulation_id}/results", response_model=SimulationResult)
async def get_simulation_results(simulation_id: str, request: Request):
    """Obtenir les résultats d'une simulation terminée."""
    simulation_manager = request.app.state.simulation_manager
    
    try:
        simulation = simulation_manager.get_simulation(simulation_id)
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation non trouvée")

        results = await simulation_manager.get_simulation_results(simulation_id)
        if not results:
            raise HTTPException(
                status_code=404, detail="Résultats non disponibles"
            )

        return SimulationResult(
            simulation_id=results.simulation_id,
            final_strategy=results.final_strategy,
            final_exploitability=results.final_exploitability,
            iterations_completed=results.iterations_completed,
            convergence_time=results.convergence_time,
            metadata=results.metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des résultats: {str(e)}")


@router.delete("/simulations/{simulation_id}")
async def cancel_simulation(simulation_id: str, request: Request):
    """Annuler une simulation en cours."""
    simulation_manager = request.app.state.simulation_manager
    
    try:
        await simulation_manager.cancel_simulation(simulation_id)
        return {"message": f"Simulation {simulation_id} annulée"}

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'annulation: {str(e)}")


# Endpoints pour les nœuds de calcul distribués
@router.get("/compute-nodes")
async def list_compute_nodes(request: Request):
    """Lister tous les nœuds de calcul."""
    compute_node_manager = request.app.state.compute_node_manager
    
    try:
        nodes = compute_node_manager.get_all_nodes()
        stats = compute_node_manager.get_cluster_stats()
        
        return {
            "compute_nodes": [node.to_dict() for node in nodes],
            "cluster_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des nœuds: {str(e)}")


@router.post("/compute-nodes/register")
async def register_compute_node(node_data: ComputeNodeRegistration, request: Request):
    """Enregistrer un nouveau nœud de calcul."""
    compute_node_manager = request.app.state.compute_node_manager
    
    try:
        result = await compute_node_manager.register_node(node_data.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/compute-nodes/{node_id}")
async def unregister_compute_node(node_id: str, request: Request):
    """Désenregistrer un nœud de calcul."""
    compute_node_manager = request.app.state.compute_node_manager
    
    try:
        result = await compute_node_manager.unregister_node(node_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/compute-nodes/{node_id}/heartbeat")
async def update_node_heartbeat(node_id: str, heartbeat_data: ComputeNodeHeartbeat, request: Request):
    """Mettre à jour le heartbeat d'un nœud."""
    compute_node_manager = request.app.state.compute_node_manager
    
    try:
        result = await compute_node_manager.update_heartbeat(node_id, heartbeat_data.dict())
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/tasks/next/{node_id}")
async def get_next_task(node_id: str, request: Request):
    """Obtenir la prochaine tâche pour un nœud."""
    compute_node_manager = request.app.state.compute_node_manager
    
    try:
        task = await compute_node_manager.get_next_task_for_node(node_id)
        if task:
            return task
        else:
            # Pas de tâches disponibles
            return {"message": "Aucune tâche disponible"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération de tâche: {str(e)}")


@router.post("/tasks/results")
async def submit_task_result(result_data: TaskResult, request: Request):
    """Soumettre le résultat d'une tâche."""
    compute_node_manager = request.app.state.compute_node_manager
    
    try:
        success = result_data.status == "completed"
        await compute_node_manager.complete_task(
            result_data.task_id,
            result_data.node_id,
            success
        )
        
        # Notifier le gestionnaire de simulation si applicable
        if result_data.result:
            # Traiter le résultat avec le simulation manager
            pass
        
        return {"message": "Résultat de tâche traité"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du résultat: {str(e)}")


@router.get("/queue/status")
async def get_queue_status(request: Request):
    """Obtenir le statut de la queue de tâches."""
    task_queue = request.app.state.task_queue
    
    try:
        status = await task_queue.get_queue_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération du statut: {str(e)}")
