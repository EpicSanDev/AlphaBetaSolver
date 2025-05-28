"""
WebSocket endpoints for real-time monitoring and updates.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Gestionnaire des connexions WebSocket."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.simulation_subscribers: Dict[str, Set[WebSocket]] = {}
        self.system_subscribers: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accepter une nouvelle connexion WebSocket."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Nouvelle connexion WebSocket: {websocket.client}")
    
    def disconnect(self, websocket: WebSocket):
        """Supprimer une connexion WebSocket."""
        self.active_connections.discard(websocket)
        self.system_subscribers.discard(websocket)
        
        # Supprimer des abonnements aux simulations
        for sim_id, subscribers in self.simulation_subscribers.items():
            subscribers.discard(websocket)
        
        logger.info(f"Connexion WebSocket fermée: {websocket.client}")
    
    async def subscribe_to_simulation(self, websocket: WebSocket, simulation_id: str):
        """Abonner une connexion aux mises à jour d'une simulation."""
        if simulation_id not in self.simulation_subscribers:
            self.simulation_subscribers[simulation_id] = set()
        self.simulation_subscribers[simulation_id].add(websocket)
        
        await self._send_to_websocket(websocket, {
            "type": "subscription_confirmed",
            "simulation_id": simulation_id,
            "timestamp": datetime.now().isoformat()
        })
    
    async def subscribe_to_system(self, websocket: WebSocket):
        """Abonner une connexion aux mises à jour système."""
        self.system_subscribers.add(websocket)
        
        await self._send_to_websocket(websocket, {
            "type": "system_subscription_confirmed",
            "timestamp": datetime.now().isoformat()
        })
    
    async def broadcast_simulation_update(self, simulation_id: str, data: dict):
        """Diffuser une mise à jour de simulation aux abonnés."""
        if simulation_id in self.simulation_subscribers:
            message = {
                "type": "simulation_update",
                "simulation_id": simulation_id,
                "data": data,
                "timestamp": datetime.now().isoformat()
            }
            
            await self._broadcast_to_subscribers(
                self.simulation_subscribers[simulation_id], 
                message
            )
    
    async def broadcast_system_update(self, data: dict):
        """Diffuser une mise à jour système aux abonnés."""
        message = {
            "type": "system_update",
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self._broadcast_to_subscribers(self.system_subscribers, message)
    
    async def broadcast_compute_node_update(self, node_data: dict):
        """Diffuser une mise à jour de nœud de calcul."""
        message = {
            "type": "compute_node_update",
            "data": node_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self._broadcast_to_subscribers(self.system_subscribers, message)
    
    async def _broadcast_to_subscribers(self, subscribers: Set[WebSocket], message: dict):
        """Diffuser un message à un ensemble d'abonnés."""
        disconnected = set()
        
        for websocket in subscribers.copy():
            try:
                await self._send_to_websocket(websocket, message)
            except Exception as e:
                logger.warning(f"Erreur lors de l'envoi WebSocket: {e}")
                disconnected.add(websocket)
        
        # Nettoyer les connexions fermées
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def _send_to_websocket(self, websocket: WebSocket, message: dict):
        """Envoyer un message à une connexion WebSocket spécifique."""
        await websocket.send_text(json.dumps(message))


# Instance globale du gestionnaire de connexions
connection_manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """Endpoint principal WebSocket pour le monitoring temps réel."""
    await connection_manager.connect(websocket)
    
    try:
        while True:
            # Écouter les messages du client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "subscribe_simulation":
                simulation_id = message.get("simulation_id")
                if simulation_id:
                    await connection_manager.subscribe_to_simulation(websocket, simulation_id)
            
            elif message_type == "subscribe_system":
                await connection_manager.subscribe_to_system(websocket)
            
            elif message_type == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }))
            
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Type de message inconnu: {message_type}"
                }))
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
        connection_manager.disconnect(websocket)


# Fonctions utilitaires pour diffuser des mises à jour
async def broadcast_simulation_progress(simulation_id: str, progress_data: dict):
    """Diffuser le progrès d'une simulation."""
    await connection_manager.broadcast_simulation_update(simulation_id, {
        "progress_percentage": progress_data.get("progress_percentage", 0),
        "iterations_completed": progress_data.get("iterations_completed", 0),
        "current_exploitability": progress_data.get("current_exploitability"),
        "estimated_time_remaining": progress_data.get("estimated_time_remaining"),
        "status": progress_data.get("status")
    })


async def broadcast_simulation_completed(simulation_id: str, results: dict):
    """Diffuser la completion d'une simulation."""
    await connection_manager.broadcast_simulation_update(simulation_id, {
        "status": "completed",
        "final_exploitability": results.get("final_exploitability"),
        "iterations_completed": results.get("iterations_completed"),
        "convergence_time": results.get("convergence_time")
    })


async def broadcast_system_metrics(metrics: dict):
    """Diffuser les métriques système."""
    await connection_manager.broadcast_system_update({
        "cpu_usage": metrics.get("cpu_usage"),
        "memory_usage": metrics.get("memory_usage"),
        "active_simulations": metrics.get("active_simulations"),
        "queue_status": metrics.get("queue_status"),
        "compute_nodes": metrics.get("compute_nodes")
    })


async def broadcast_new_compute_node(node_info: dict):
    """Diffuser l'arrivée d'un nouveau nœud de calcul."""
    await connection_manager.broadcast_compute_node_update({
        "event": "node_connected",
        "node": node_info
    })


async def broadcast_compute_node_disconnected(node_id: str):
    """Diffuser la déconnexion d'un nœud de calcul."""
    await connection_manager.broadcast_compute_node_update({
        "event": "node_disconnected",
        "node_id": node_id
    })
