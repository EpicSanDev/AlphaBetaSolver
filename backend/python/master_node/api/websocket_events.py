"""
Module d'événements WebSocket pour éviter les imports circulaires.
"""

import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Queue globale pour les événements WebSocket
websocket_events = asyncio.Queue()

async def broadcast_compute_node_event(event_type: str, data: Dict[str, Any]):
    """Ajouter un événement de nœud de calcul à la queue."""
    try:
        await websocket_events.put({
            "type": "compute_node_event",
            "event": event_type,
            "data": data
        })
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de l'événement WebSocket: {e}")

async def broadcast_simulation_event(event_type: str, data: Dict[str, Any]):
    """Ajouter un événement de simulation à la queue."""
    try:
        await websocket_events.put({
            "type": "simulation_event", 
            "event": event_type,
            "data": data
        })
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de l'événement WebSocket: {e}")

async def broadcast_system_event(event_type: str, data: Dict[str, Any]):
    """Ajouter un événement système à la queue."""
    try:
        await websocket_events.put({
            "type": "system_event",
            "event": event_type,
            "data": data
        })
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout de l'événement WebSocket: {e}")
