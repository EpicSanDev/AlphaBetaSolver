"""
Gestionnaire de files de tâches avec RabbitMQ pour la distribution des calculs.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
import aio_pika
from aio_pika import ExchangeType
from ..core.config import settings

logger = logging.getLogger(__name__)

class TaskQueue:
    """Gestionnaire de files de tâches RabbitMQ."""
    
    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.connected = False
    
    async def connect(self):
        """Établir la connexion à RabbitMQ."""
        if self.connected:
            return
            
        try:
            rabbitmq_url = f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/"
            self.connection = await aio_pika.connect_robust(rabbitmq_url)
            self.channel = await self.connection.channel()
            
            # Déclarer les queues
            await self.channel.declare_queue(settings.RABBITMQ_QUEUE_PREFLOP, durable=True)
            await self.channel.declare_queue(settings.RABBITMQ_QUEUE_POSTFLOP, durable=True)
            await self.channel.declare_queue("computation_results", durable=True)
            
            self.connected = True
            logger.info(f"Connecté à RabbitMQ: {rabbitmq_url}")
            
        except Exception as e:
            logger.error(f"Erreur de connexion à RabbitMQ: {e}")
            raise
    
    async def publish_task(self, simulation_type: str, task_data: Dict[str, Any]) -> bool:
        """Publier une tâche dans la file appropriée."""
        if not self.connected:
            await self.connect()
        
        try:
            # Choisir la queue selon le type de simulation
            queue_name = (settings.RABBITMQ_QUEUE_PREFLOP 
                         if simulation_type == "preflop" 
                         else settings.RABBITMQ_QUEUE_POSTFLOP)
            
            message = aio_pika.Message(
                json.dumps(task_data).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            )
            
            await self.channel.default_exchange.publish(
                message,
                routing_key=queue_name
            )
            
            logger.info(f"Tâche publiée dans {queue_name}: {task_data.get('task_id', 'N/A')}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la publication de la tâche: {e}")
            return False
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Obtenir le statut des files de messages."""
        if not self.connected:
            await self.connect()
        
        try:
            # Declare queues to get their status  
            preflop_queue = await self.channel.declare_queue(settings.RABBITMQ_QUEUE_PREFLOP, durable=True, passive=True)
            postflop_queue = await self.channel.declare_queue(settings.RABBITMQ_QUEUE_POSTFLOP, durable=True, passive=True)
            results_queue = await self.channel.declare_queue("computation_results", durable=True, passive=True)
            
            return {
                "preflop_tasks": preflop_queue.declaration_result.message_count,
                "postflop_tasks": postflop_queue.declaration_result.message_count,
                "pending_results": results_queue.declaration_result.message_count,
                "connected": self.connected
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du statut des files: {e}")
            return {"error": str(e), "connected": self.connected}
    
    async def get_detailed_queue_status(self) -> Dict[str, Any]:
        """Statut détaillé des files de messages."""
        basic_status = await self.get_queue_status()
        
        return {
            **basic_status,
            "rabbitmq_host": settings.RABBITMQ_HOST,
            "rabbitmq_port": settings.RABBITMQ_PORT,
            "queues": {
                "preflop": settings.RABBITMQ_QUEUE_PREFLOP,
                "postflop": settings.RABBITMQ_QUEUE_POSTFLOP,
                "results": "computation_results"
            }
        }
    
    async def consume_results(self, callback):
        """Consommer les résultats de calcul."""
        if not self.connected:
            await self.connect()
        
        results_queue = await self.channel.get_queue("computation_results")
        
        async with results_queue.iterator() as queue_iter:
            async for message in queue_iter:
                try:
                    result_data = json.loads(message.body.decode())
                    await callback(result_data)
                    await message.ack()
                except Exception as e:
                    logger.error(f"Erreur lors du traitement du résultat: {e}")
                    await message.nack(requeue=False)
    
    async def close(self):
        """Fermer la connexion."""
        if self.connection:
            await self.connection.close()
            self.connected = False
    
    async def disconnect(self):
        """Alias for close() method for backward compatibility."""
        await self.close()
