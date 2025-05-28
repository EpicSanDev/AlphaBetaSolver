"""
Gestionnaire des nœuds de calcul distribués.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ComputeNode:
    """Représentation d'un nœud de calcul."""
    node_id: str
    platform: str
    architecture: str
    cpu_count: int
    memory_total: int
    max_concurrent_tasks: int
    current_tasks: int = 0
    status: str = "available"  # available, busy, offline
    last_heartbeat: Optional[datetime] = None
    registration_time: Optional[datetime] = None
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir en dictionnaire pour l'API."""
        data = asdict(self)
        # Convertir les datetime en ISO string
        if self.last_heartbeat:
            data['last_heartbeat'] = self.last_heartbeat.isoformat()
        if self.registration_time:
            data['registration_time'] = self.registration_time.isoformat()
        return data


class ComputeNodeManager:
    """Gestionnaire des nœuds de calcul distribués."""
    
    def __init__(self):
        self.nodes: Dict[str, ComputeNode] = {}
        self.task_assignments: Dict[str, str] = {}  # task_id -> node_id
        self.pending_tasks = asyncio.Queue()
        self.heartbeat_timeout = timedelta(minutes=2)
        self.cleanup_task = None
        
        # Démarrer la tâche de nettoyage
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def register_node(self, node_data: Dict[str, Any]) -> Dict[str, str]:
        """Enregistrer un nouveau nœud de calcul."""
        node_id = node_data.get("node_id")
        
        if not node_id:
            raise ValueError("node_id requis")
        
        # Créer ou mettre à jour le nœud
        node = ComputeNode(
            node_id=node_id,
            platform=node_data.get("platform", "unknown"),
            architecture=node_data.get("architecture", "unknown"),
            cpu_count=node_data.get("cpu_count", 1),
            memory_total=node_data.get("memory_total", 0),
            max_concurrent_tasks=node_data.get("max_concurrent_tasks", 1),
            current_tasks=node_data.get("current_tasks", 0),
            status=node_data.get("status", "available"),
            registration_time=datetime.now(),
            last_heartbeat=datetime.now()
        )
        
        self.nodes[node_id] = node
        
        logger.info(f"Nœud enregistré: {node_id} ({node.platform} {node.architecture}, {node.cpu_count} CPUs)")
        
        # Diffuser la nouvelle connexion via WebSocket
        try:
            from ..api.websocket import broadcast_new_compute_node
            await broadcast_new_compute_node(node.to_dict())
        except ImportError:
            logger.warning("WebSocket broadcasting not available")
        
        return {"message": f"Nœud {node_id} enregistré avec succès"}
    
    async def unregister_node(self, node_id: str) -> Dict[str, str]:
        """Désenregistrer un nœud de calcul."""
        if node_id in self.nodes:
            del self.nodes[node_id]
            
            # Nettoyer les assignations de tâches
            tasks_to_remove = [task_id for task_id, assigned_node in self.task_assignments.items() 
                             if assigned_node == node_id]
            for task_id in tasks_to_remove:
                del self.task_assignments[task_id]
                logger.warning(f"Tâche {task_id} réassignée suite à la déconnexion du nœud {node_id}")
            
            logger.info(f"Nœud désenregistré: {node_id}")
            
            # Diffuser la déconnexion via WebSocket
            try:
                from ..api.websocket import broadcast_compute_node_disconnected
                await broadcast_compute_node_disconnected(node_id)
            except ImportError:
                logger.warning("WebSocket broadcasting not available")
            
            return {"message": f"Nœud {node_id} désenregistré"}
        else:
            raise ValueError(f"Nœud {node_id} non trouvé")
    
    async def update_heartbeat(self, node_id: str, heartbeat_data: Dict[str, Any]) -> Dict[str, str]:
        """Mettre à jour le heartbeat d'un nœud."""
        if node_id not in self.nodes:
            raise ValueError(f"Nœud {node_id} non enregistré")
        
        node = self.nodes[node_id]
        node.last_heartbeat = datetime.now()
        node.current_tasks = heartbeat_data.get("current_tasks", node.current_tasks)
        node.status = heartbeat_data.get("status", node.status)
        node.cpu_usage = heartbeat_data.get("cpu_usage", 0.0)
        node.memory_usage = heartbeat_data.get("memory_usage", 0.0)
        
        return {"message": "Heartbeat mis à jour"}
    
    def get_available_nodes(self) -> List[ComputeNode]:
        """Obtenir la liste des nœuds disponibles pour de nouvelles tâches."""
        now = datetime.now()
        available_nodes = []
        
        for node in self.nodes.values():
            # Vérifier que le nœud est vivant
            if node.last_heartbeat and (now - node.last_heartbeat) < self.heartbeat_timeout:
                # Vérifier qu'il a de la capacité
                if node.current_tasks < node.max_concurrent_tasks and node.status == "available":
                    available_nodes.append(node)
        
        # Trier par disponibilité (moins de tâches en cours d'abord)
        available_nodes.sort(key=lambda n: n.current_tasks)
        
        return available_nodes
    
    def get_all_nodes(self) -> List[ComputeNode]:
        """Obtenir tous les nœuds avec leur statut."""
        now = datetime.now()
        nodes = []
        
        for node in self.nodes.values():
            # Marquer comme offline si pas de heartbeat récent
            if node.last_heartbeat and (now - node.last_heartbeat) >= self.heartbeat_timeout:
                node.status = "offline"
            
            nodes.append(node)
        
        return nodes
    
    async def assign_task(self, task_id: str, task_data: Dict[str, Any]) -> Optional[str]:
        """Assigner une tâche à un nœud disponible."""
        available_nodes = self.get_available_nodes()
        
        if not available_nodes:
            # Pas de nœuds disponibles, mettre en queue
            await self.pending_tasks.put((task_id, task_data))
            return None
        
        # Sélectionner le nœud le moins chargé
        selected_node = available_nodes[0]
        
        # Assigner la tâche
        self.task_assignments[task_id] = selected_node.node_id
        selected_node.current_tasks += 1
        
        # Mettre à jour le statut si nécessaire
        if selected_node.current_tasks >= selected_node.max_concurrent_tasks:
            selected_node.status = "busy"
        
        logger.info(f"Tâche {task_id} assignée au nœud {selected_node.node_id}")
        
        return selected_node.node_id
    
    async def complete_task(self, task_id: str, node_id: str, success: bool = True):
        """Marquer une tâche comme terminée."""
        if task_id in self.task_assignments:
            del self.task_assignments[task_id]
        
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.current_tasks = max(0, node.current_tasks - 1)
            
            if success:
                node.total_tasks_completed += 1
            else:
                node.total_tasks_failed += 1
            
            # Remettre le nœud disponible si il ne l'était pas
            if node.current_tasks < node.max_concurrent_tasks:
                node.status = "available"
        
        # Traiter les tâches en attente
        await self._process_pending_tasks()
    
    async def get_next_task_for_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Obtenir la prochaine tâche pour un nœud spécifique."""
        if node_id not in self.nodes:
            return None
        
        node = self.nodes[node_id]
        
        # Vérifier la capacité
        if node.current_tasks >= node.max_concurrent_tasks:
            return None
        
        # Essayer de prendre une tâche de la queue
        try:
            task_id, task_data = await asyncio.wait_for(self.pending_tasks.get(), timeout=1.0)
            
            # Assigner la tâche
            self.task_assignments[task_id] = node_id
            node.current_tasks += 1
            
            if node.current_tasks >= node.max_concurrent_tasks:
                node.status = "busy"
            
            return {
                "task_id": task_id,
                **task_data
            }
            
        except asyncio.TimeoutError:
            return None
    
    async def _process_pending_tasks(self):
        """Traiter les tâches en attente."""
        available_nodes = self.get_available_nodes()
        
        while available_nodes and not self.pending_tasks.empty():
            try:
                task_id, task_data = await asyncio.wait_for(self.pending_tasks.get(), timeout=0.1)
                
                # Sélectionner un nœud
                node = available_nodes[0]
                
                # Assigner la tâche
                self.task_assignments[task_id] = node.node_id
                node.current_tasks += 1
                
                if node.current_tasks >= node.max_concurrent_tasks:
                    node.status = "busy"
                    available_nodes.remove(node)
                
                logger.info(f"Tâche en attente {task_id} assignée au nœud {node.node_id}")
                
            except asyncio.TimeoutError:
                break
    
    async def _cleanup_loop(self):
        """Boucle de nettoyage pour supprimer les nœuds inactifs."""
        while True:
            try:
                await asyncio.sleep(60)  # Nettoyer toutes les minutes
                
                now = datetime.now()
                inactive_nodes = []
                
                for node_id, node in self.nodes.items():
                    if node.last_heartbeat and (now - node.last_heartbeat) > self.heartbeat_timeout * 2:
                        inactive_nodes.append(node_id)
                
                # Supprimer les nœuds inactifs
                for node_id in inactive_nodes:
                    logger.warning(f"Suppression du nœud inactif: {node_id}")
                    await self.unregister_node(node_id)
                
            except Exception as e:
                logger.error(f"Erreur dans la boucle de nettoyage: {e}")
    
    def get_cluster_stats(self) -> Dict[str, Any]:
        """Obtenir les statistiques du cluster."""
        active_nodes = [n for n in self.nodes.values() 
                       if n.last_heartbeat and 
                       (datetime.now() - n.last_heartbeat) < self.heartbeat_timeout]
        
        total_capacity = sum(n.max_concurrent_tasks for n in active_nodes)
        current_usage = sum(n.current_tasks for n in active_nodes)
        total_completed = sum(n.total_tasks_completed for n in active_nodes)
        total_failed = sum(n.total_tasks_failed for n in active_nodes)
        
        return {
            "total_nodes": len(self.nodes),
            "active_nodes": len(active_nodes),
            "total_capacity": total_capacity,
            "current_usage": current_usage,
            "utilization_percentage": (current_usage / total_capacity * 100) if total_capacity > 0 else 0,
            "pending_tasks": self.pending_tasks.qsize(),
            "total_tasks_completed": total_completed,
            "total_tasks_failed": total_failed,
            "success_rate": (total_completed / (total_completed + total_failed) * 100) 
                          if (total_completed + total_failed) > 0 else 0
        }

    async def cleanup(self):
        """Nettoyer les ressources du gestionnaire."""
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Compute node manager cleaned up")


# Instance globale
compute_node_manager = None

def get_compute_node_manager() -> ComputeNodeManager:
    """Get or create the global compute node manager instance."""
    global compute_node_manager
    if compute_node_manager is None:
        compute_node_manager = ComputeNodeManager()
    return compute_node_manager
