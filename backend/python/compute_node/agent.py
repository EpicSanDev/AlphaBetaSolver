"""
Agent de calcul pour les nœuds de calcul distribués.
Consomme les tâches de la file RabbitMQ et exécute les simulations C++.
"""

import asyncio
import json
import logging
import tempfile
import os
from typing import Dict, Any, Optional
import aio_pika
from pydantic import BaseModel

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskConfig(BaseModel):
    """Configuration d'une tâche de simulation."""

    task_id: str
    task_type: str  # "preflop" ou "postflop"
    simulation_params: Dict[str, Any]
    cpp_binary_path: str = "/app/build/src/PokerSolver"


class TaskResult(BaseModel):
    """Résultat d'une tâche de simulation."""

    task_id: str
    success: bool
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: int


class ComputeAgent:
    """Agent de calcul qui consomme les tâches et exécute les simulations."""

    def __init__(
        self,
        rabbitmq_url: str = "amqp://guest:guest@localhost/",
        queue_name: str = "computation_tasks",
        result_queue: str = "computation_results",
    ):
        self.rabbitmq_url = rabbitmq_url
        self.queue_name = queue_name
        self.result_queue = result_queue
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.running = False

    async def connect(self):
        """Établir la connexion à RabbitMQ."""
        try:
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()

            # Déclarer les queues
            await self.channel.declare_queue(self.queue_name, durable=True)
            await self.channel.declare_queue(self.result_queue, durable=True)

            logger.info(f"Connecté à RabbitMQ: {self.rabbitmq_url}")
        except Exception as e:
            logger.error(f"Erreur de connexion à RabbitMQ: {e}")
            raise

    async def start_consuming(self):
        """Démarrer la consommation des tâches."""
        if not self.channel:
            await self.connect()

        queue = await self.channel.get_queue(self.queue_name)

        self.running = True
        logger.info(f"Démarrage de la consommation des tâches depuis {self.queue_name}")

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self.running:
                    break

                try:
                    await self.process_message(message)
                except Exception as e:
                    logger.error(
                        f"Erreur lors du traitement du message: {e}"
                    )
                    await message.nack(requeue=False)

    async def process_message(self, message: aio_pika.IncomingMessage):
        """Traiter un message de tâche."""
        try:
            # Décoder la tâche
            task_data = json.loads(message.body.decode())
            task_config = TaskConfig(**task_data)

            logger.info(f"Traitement de la tâche {task_config.task_id}")

            # Exécuter la simulation
            result = await self.execute_simulation(task_config)

            # Envoyer le résultat
            await self.send_result(result)

            # Acquitter le message
            await message.ack()

            logger.info(f"Tâche {task_config.task_id} terminée avec succès")

        except Exception as e:
            logger.error(f"Erreur lors du traitement de la tâche: {e}")
            await message.nack(requeue=False)

    async def execute_simulation(self, task_config: TaskConfig) -> TaskResult:
        """Exécuter une simulation en appelant le binaire C++."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Créer un fichier temporaire avec les paramètres
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(task_config.simulation_params, f)
                params_file = f.name

            try:
                # Construire la commande
                cmd = [
                    task_config.cpp_binary_path,
                    "--task-type",
                    task_config.task_type,
                    "--params-file",
                    params_file,
                    "--output-format",
                    "json",
                ]

                # Exécuter le processus C++
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    # Analyser la sortie JSON
                    result_data = json.loads(stdout.decode())

                    execution_time = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )

                    return TaskResult(
                        task_id=task_config.task_id,
                        success=True,
                        result_data=result_data,
                        execution_time_ms=execution_time,
                    )
                else:
                    error_msg = stderr.decode() if stderr else "Erreur inconnue"
                    execution_time = int(
                        (asyncio.get_event_loop().time() - start_time) * 1000
                    )

                    return TaskResult(
                        task_id=task_config.task_id,
                        success=False,
                        error_message=(
                            f"Le processus a échoué avec le code "
                            f"{process.returncode}: {error_msg}"
                        ),
                        execution_time_ms=execution_time,
                    )

            finally:
                # Nettoyer le fichier temporaire
                if os.path.exists(params_file):
                    os.unlink(params_file)

        except Exception as e:
            execution_time = int(
                (asyncio.get_event_loop().time() - start_time) * 1000
            )
            return TaskResult(
                task_id=task_config.task_id,
                success=False,
                error_message=str(e),
                execution_time_ms=execution_time,
            )

    async def send_result(self, result: TaskResult):
        """Envoyer le résultat vers la queue des résultats."""
        if not self.channel:
            raise RuntimeError("Canal RabbitMQ non initialisé")

        result_message = aio_pika.Message(
            result.json().encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )

        await self.channel.default_exchange.publish(
            result_message, routing_key=self.result_queue
        )

    async def stop(self):
        """Arrêter l'agent de calcul."""
        self.running = False
        if self.connection:
            await self.connection.close()
        logger.info("Agent de calcul arrêté")


async def main():
    """Point d'entrée principal de l'agent de calcul."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Agent de calcul pour le solveur GTO"
    )
    parser.add_argument(
        "--rabbitmq-url",
        default="amqp://guest:guest@localhost/",
        help="URL de connexion RabbitMQ",
    )
    parser.add_argument(
        "--queue-name",
        default="computation_tasks",
        help="Nom de la queue des tâches"
    )
    parser.add_argument(
        "--result-queue",
        default="computation_results",
        help="Nom de la queue des résultats",
    )

    args = parser.parse_args()

    agent = ComputeAgent(
        rabbitmq_url=args.rabbitmq_url,
        queue_name=args.queue_name,
        result_queue=args.result_queue,
    )

    try:
        await agent.start_consuming()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
