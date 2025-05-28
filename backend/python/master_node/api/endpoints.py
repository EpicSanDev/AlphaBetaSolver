"""
API endpoints pour le noeud maître du solveur GTO.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

# Models Pydantic
class SimulationRequest(BaseModel):
    simulation_type: str
    game_config: Dict[str, Any]
    solver_config: Dict[str, Any]
    name: Optional[str] = None
    description: Optional[str] = None

class ComputeNodeRegistration(BaseModel):
    node_id: str
    platform: str
    architecture: str
    cpu_count: int
    memory_total: int
    max_concurrent_tasks: int

class HeartbeatData(BaseModel):
    current_tasks: int
    status: str
    cpu_usage: float
    memory_usage: float

class TaskResult(BaseModel):
    task_id: str
    node_id: str
    success: bool
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

# Dependency pour accéder aux services
def get_simulation_manager(request: Request):
    return request.app.state.simulation_manager

def get_compute_node_manager(request: Request):
    return request.app.state.compute_node_manager

def get_task_queue(request: Request):
    return request.app.state.task_queue

# Endpoints pour les simulations
@router.post("/simulations")
async def create_simulation(
    simulation_request: SimulationRequest,
    simulation_manager = Depends(get_simulation_manager)
):
    """Créer une nouvelle simulation."""
    try:
        import uuid
        simulation_id = str(uuid.uuid4())
        
        simulation = await simulation_manager.create_simulation(
            simulation_id=simulation_id,
            simulation_type=simulation_request.simulation_type,
            game_config=simulation_request.game_config,
            solver_config=simulation_request.solver_config,
            name=simulation_request.name,
            description=simulation_request.description
        )
        
        # Démarrer la simulation
        await simulation_manager.start_simulation(simulation_id)
        
        return {
            "simulation_id": simulation_id,
            "status": "created",
            "message": "Simulation créée et démarrée avec succès"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de la simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/simulations")
async def list_simulations(
    status: Optional[str] = None,
    simulation_manager = Depends(get_simulation_manager)
):
    """Lister les simulations."""
    try:
        simulations = await simulation_manager.list_simulations(status_filter=status)
        
        return [
            {
                "simulation_id": sim.simulation_id,
                "simulation_type": sim.simulation_type,
                "status": sim.status.value,
                "created_at": sim.created_at.isoformat(),
                "name": sim.name,
                "description": sim.description,
                "progress_percentage": sim.progress_percentage
            }
            for sim in simulations
        ]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des simulations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/simulations/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    simulation_manager = Depends(get_simulation_manager)
):
    """Obtenir les détails d'une simulation."""
    try:
        simulation = await simulation_manager.get_simulation_status(simulation_id)
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation non trouvée")
        
        return {
            "simulation_id": simulation.simulation_id,
            "simulation_type": simulation.simulation_type,
            "status": simulation.status.value,
            "created_at": simulation.created_at.isoformat(),
            "updated_at": simulation.updated_at.isoformat(),
            "name": simulation.name,
            "description": simulation.description,
            "progress_percentage": simulation.progress_percentage,
            "iterations_completed": simulation.iterations_completed,
            "current_exploitability": simulation.current_exploitability,
            "estimated_time_remaining": simulation.estimated_time_remaining,
            "game_config": simulation.game_config,
            "solver_config": simulation.solver_config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/simulations/{simulation_id}/status")
async def get_simulation_status(
    simulation_id: str,
    simulation_manager = Depends(get_simulation_manager)
):
    """Obtenir le statut d'une simulation."""
    try:
        simulation = await simulation_manager.get_simulation_status(simulation_id)
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation non trouvée")
        
        return {
            "simulation_id": simulation_id,
            "status": simulation.status.value,
            "progress_percentage": simulation.progress_percentage,
            "iterations_completed": simulation.iterations_completed,
            "current_exploitability": simulation.current_exploitability,
            "estimated_time_remaining": simulation.estimated_time_remaining,
            "updated_at": simulation.updated_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulations/{simulation_id}/cancel")
async def cancel_simulation(
    simulation_id: str,
    simulation_manager = Depends(get_simulation_manager)
):
    """Annuler une simulation."""
    try:
        await simulation_manager.cancel_simulation(simulation_id)
        return {"message": "Simulation annulée"}
        
    except Exception as e:
        logger.error(f"Erreur lors de l'annulation de la simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints pour les nœuds de calcul
@router.post("/compute-nodes/register")
async def register_compute_node(
    node_data: ComputeNodeRegistration,
    compute_node_manager = Depends(get_compute_node_manager)
):
    """Enregistrer un nœud de calcul."""
    try:
        result = await compute_node_manager.register_node(node_data.dict())
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement du nœud: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compute-nodes/{node_id}/heartbeat")
async def update_heartbeat(
    node_id: str,
    heartbeat_data: HeartbeatData,
    compute_node_manager = Depends(get_compute_node_manager)
):
    """Mettre à jour le heartbeat d'un nœud."""
    try:
        result = await compute_node_manager.update_heartbeat(node_id, heartbeat_data.dict())
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du heartbeat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compute-nodes")
async def get_compute_nodes(
    compute_node_manager = Depends(get_compute_node_manager)
):
    """Obtenir la liste des nœuds de calcul."""
    try:
        nodes = compute_node_manager.get_all_nodes()
        cluster_stats = compute_node_manager.get_cluster_stats()
        
        return {
            "compute_nodes": [node.to_dict() for node in nodes],
            "cluster_stats": cluster_stats
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des nœuds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tasks/next")
async def get_next_task(
    node_id: str,
    compute_node_manager = Depends(get_compute_node_manager)
):
    """Obtenir la prochaine tâche pour un nœud."""
    try:
        task = await compute_node_manager.get_next_task_for_node(node_id)
        if task:
            return task
        else:
            return {"message": "Aucune tâche disponible"}
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la tâche: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/results")
async def submit_task_result(
    task_result: TaskResult,
    compute_node_manager = Depends(get_compute_node_manager)
):
    """Soumettre le résultat d'une tâche."""
    try:
        await compute_node_manager.complete_task(
            task_result.task_id,
            task_result.node_id,
            task_result.success
        )
        
        return {"message": "Résultat de tâche soumis avec succès"}
        
    except Exception as e:
        logger.error(f"Erreur lors de la soumission du résultat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints de statut système
@router.get("/status")
async def get_system_status(
    simulation_manager = Depends(get_simulation_manager),
    compute_node_manager = Depends(get_compute_node_manager)
):
    """Obtenir le statut du système."""
    try:
        simulations = await simulation_manager.list_simulations()
        active_simulations = len([
            sim for sim in simulations
            if sim.status.value in ['running', 'pending']
        ])
        
        cluster_stats = compute_node_manager.get_cluster_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "active_simulations": active_simulations,
            "cluster_stats": cluster_stats
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/queue/status")
async def get_queue_status(
    task_queue = Depends(get_task_queue),
    compute_node_manager = Depends(get_compute_node_manager)
):
    """Obtenir le statut des files d'attente."""
    try:
        return {
            "connected": True,  # TODO: Implement actual queue status check
            "preflop_tasks": 0,  # TODO: Get actual queue sizes
            "postflop_tasks": 0,
            "pending_results": 0,
            "pending_tasks": compute_node_manager.pending_tasks.qsize()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut des files: {e}")
        raise HTTPException(status_code=500, detail=str(e))