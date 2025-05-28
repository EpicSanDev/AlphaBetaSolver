"""
Gestionnaire de simulations pour orchestrer les calculs distribués.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import aiofiles
import os
from .task_queue import TaskQueue

logger = logging.getLogger(__name__)


class SimulationStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Simulation:
    simulation_id: str
    simulation_type: str  # "preflop" ou "postflop"
    status: SimulationStatus
    created_at: datetime
    updated_at: datetime
    game_config: Dict[str, Any]
    solver_config: Dict[str, Any]
    name: Optional[str] = None
    description: Optional[str] = None
    estimated_completion_time: Optional[datetime] = None
    progress_percentage: float = 0.0
    iterations_completed: int = 0
    current_exploitability: Optional[float] = None
    estimated_time_remaining: Optional[int] = None
    task_ids: List[str] = None

    def __post_init__(self):
        if self.task_ids is None:
            self.task_ids = []


@dataclass
class SimulationResults:
    simulation_id: str
    final_strategy: Dict[str, Any]
    final_exploitability: float
    iterations_completed: int
    convergence_time: float
    metadata: Dict[str, Any]


class SimulationManager:
    """Gestionnaire central des simulations GTO."""

    def __init__(
        self,
        task_queue: TaskQueue = None,
        storage_path: str = "/tmp/gto_simulations"
    ):
        self.simulations: Dict[str, Simulation] = {}
        self.results: Dict[str, SimulationResults] = {}
        self.task_queue = task_queue if task_queue is not None else TaskQueue()
        self.storage_path = storage_path
        self.running_simulations: Dict[str, asyncio.Task] = {}
        self.results_consumer_task: Optional[asyncio.Task] = None # Ajout pour le consommateur de résultats

        # Créer le répertoire de stockage
        os.makedirs(storage_path, exist_ok=True)

    async def start(self):
        """Démarrer le gestionnaire de simulations."""
        if (
            hasattr(self.task_queue, "connected") and
            not self.task_queue.connected
        ):
            await self.task_queue.connect()
        
        # Lancer le consommateur de résultats une seule fois en tâche de fond
        if self.results_consumer_task is None or self.results_consumer_task.done():
            if not self.task_queue.connected: # S'assurer que la connexion est établie
                await self.task_queue.connect()
            self.results_consumer_task = asyncio.create_task(
                self.task_queue.consume_results(self._process_task_result_global)
            )
            logger.info("Results consumer task started.")
        
        logger.info("Simulation manager started")

    async def stop(self):
        """Arrêter le gestionnaire de simulations."""
        # Annuler la tâche de consommation des résultats
        if self.results_consumer_task and not self.results_consumer_task.done():
            self.results_consumer_task.cancel()
            try:
                await self.results_consumer_task
            except asyncio.CancelledError:
                logger.info("Results consumer task cancelled.")
        
        # Annuler toutes les simulations en cours
        for simulation_id, task in self.running_simulations.items():
            if not task.done():
                task.cancel()

        # Attendre que toutes les tâches se terminent
        if self.running_simulations:
            await asyncio.gather(
                *self.running_simulations.values(), return_exceptions=True
            )

        logger.info("Simulation manager stopped")

    async def create_simulation(
        self,
        simulation_id: str,
        simulation_type: str,
        game_config: Dict[str, Any],
        solver_config: Dict[str, Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Simulation:
        """Créer une nouvelle simulation."""

        # Estimer le temps de completion basé sur les paramètres
        estimated_time = self._estimate_completion_time(simulation_type, solver_config)

        simulation = Simulation(
            simulation_id=simulation_id,
            simulation_type=simulation_type,
            status=SimulationStatus.PENDING,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            game_config=game_config,
            solver_config=solver_config,
            name=name,
            description=description,
            estimated_completion_time=estimated_time
        )

        self.simulations[simulation_id] = simulation
        await self._save_simulation(simulation)

        logger.info(f"Simulation créée: {simulation_id} ({simulation_type})")
        return simulation

    def _estimate_completion_time(
        self, simulation_type: str, solver_config: Dict[str, Any]
    ) -> datetime:
        """Estimer le temps de completion d'une simulation."""
        # Estimation basique - à améliorer avec des métriques réelles
        base_minutes = 30 if simulation_type == "preflop" else 120
        max_iterations = solver_config.get("max_iterations", 1000)
        complexity_factor = max_iterations / 1000

        estimated_minutes = base_minutes * complexity_factor
        return datetime.now() + timedelta(minutes=estimated_minutes)

    async def start_simulation(self, simulation_id: str):
        """Démarrer une simulation en arrière-plan."""
        simulation = self.simulations.get(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} non trouvée")

        simulation.status = SimulationStatus.RUNNING
        simulation.updated_at = datetime.now()
        await self._save_simulation(simulation)

        # Créer la tâche asynchrone pour la simulation
        task = asyncio.create_task(self._run_simulation(simulation))
        self.running_simulations[simulation_id] = task

        logger.info(f"Simulation démarrée: {simulation_id}")

    async def _run_simulation(self, simulation: Simulation):
        """Exécuter une simulation de bout en bout."""
        try:
            # Décomposer la simulation en sous-tâches
            tasks = await self._decompose_simulation(simulation)

            # Publier les tâches dans la file
            for task_data in tasks:
                success = await self.task_queue.publish_task(
                    simulation.simulation_type, task_data
                )
                if success:
                    simulation.task_ids.append(task_data["task_id"])

            await self._save_simulation(simulation)

            # Surveiller l'avancement
            await self._monitor_simulation_progress(simulation)

        except Exception as e:
            logger.error(
                f"Erreur lors de l'exécution de la simulation "
                f"{simulation.simulation_id}: {e}"
            )
            simulation.status = SimulationStatus.FAILED
            simulation.updated_at = datetime.now()
            await self._save_simulation(simulation)
        finally:
            # Nettoyer les références
            if simulation.simulation_id in self.running_simulations:
                del self.running_simulations[simulation.simulation_id]

    async def _decompose_simulation(
        self, simulation: Simulation
    ) -> List[Dict[str, Any]]:
        """Décomposer une simulation en sous-tâches."""
        tasks = []
        max_iterations = simulation.solver_config.get("max_iterations", 1000)
        batch_size = simulation.solver_config.get("batch_size", 100)

        num_batches = max(1, max_iterations // batch_size)

        for i in range(num_batches):
            task_id = f"{simulation.simulation_id}_batch_{i}"
            start_iteration = i * batch_size
            end_iteration = min((i + 1) * batch_size, max_iterations)

            task_data = {
                "task_id": task_id,
                "simulation_id": simulation.simulation_id,
                "task_type": simulation.simulation_type,
                "simulation_params": {
                    "game_config": simulation.game_config,
                    "solver_config": {
                        **simulation.solver_config,
                        "start_iteration": start_iteration,
                        "end_iteration": end_iteration,
                    },
                },
                "cpp_binary_path": "/app/build/src/PokerSolver",
            }

            tasks.append(task_data)

        logger.info(
            f"Simulation {simulation.simulation_id} décomposée en {len(tasks)} tâches"
        )
        return tasks

    async def _monitor_simulation_progress(self, simulation: Simulation):
        """Surveiller l'avancement d'une simulation."""
        completed_tasks = 0
        total_tasks = len(simulation.task_ids)

        if total_tasks == 0:
            logger.warning(f"Simulation {simulation.simulation_id} n'a aucune tâche à monitorer.")
            simulation.status = SimulationStatus.COMPLETED 
            simulation.progress_percentage = 100.0
            simulation.updated_at = datetime.now()
            await self._save_simulation(simulation)
            logger.info(f"Simulation {simulation.simulation_id} considérée comme terminée (aucune tâche).")
            return

        # La consommation des résultats est gérée globalement par self.results_consumer_task
        # lancée dans la méthode start() du SimulationManager.

        logger.info(f"Monitoring progress for simulation {simulation.simulation_id} with {total_tasks} tasks.")
        while completed_tasks < total_tasks:
            await asyncio.sleep(10)  # Vérifier toutes les 10 secondes

            if simulation.status == SimulationStatus.CANCELLED:
                logger.info(f"Monitoring de {simulation.simulation_id} arrêté car annulée.")
                break
            if simulation.status == SimulationStatus.FAILED:
                logger.info(f"Monitoring de {simulation.simulation_id} arrêté car échouée.")
                break
            
            # Calculer le progrès
            current_completed_tasks = await self._count_completed_tasks(
                simulation.simulation_id
            )
            # S'assurer que completed_tasks ne dépasse pas total_tasks
            completed_tasks = min(current_completed_tasks, total_tasks)
            
            new_progress_percentage = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0

            if simulation.progress_percentage != new_progress_percentage:
                 logger.info(f"Simulation {simulation.simulation_id} progress: {new_progress_percentage:.2f}% ({completed_tasks}/{total_tasks})")
            
            simulation.progress_percentage = new_progress_percentage
            simulation.iterations_completed = completed_tasks # Approximation, dépend de la granularité des tâches
            simulation.updated_at = datetime.now()

            # Estimer le temps restant
            if completed_tasks > 0 and simulation.status == SimulationStatus.RUNNING:
                elapsed_time_since_creation = (datetime.now() - simulation.created_at).total_seconds()
                elapsed_time_since_creation = max(0, elapsed_time_since_creation)

                estimated_total_time = elapsed_time_since_creation * total_tasks / completed_tasks
                time_remaining = int(estimated_total_time - elapsed_time_since_creation)
                simulation.estimated_time_remaining = max(0, time_remaining)
            elif completed_tasks == 0 and simulation.status == SimulationStatus.RUNNING:
                # Si aucune tâche n'est encore complétée, on ne peut pas estimer, ou on utilise l'estimation initiale
                pass


            await self._save_simulation(simulation)


        # Après la boucle
        if simulation.status == SimulationStatus.RUNNING: # Si toujours RUNNING, c'est qu'elle est complétée
            logger.info(f"Simulation {simulation.simulation_id} a complété toutes ses tâches ({completed_tasks}/{total_tasks}). Agrégation des résultats.")
            await self._aggregate_results(simulation)
            simulation.status = SimulationStatus.COMPLETED
            simulation.progress_percentage = 100.0
            simulation.updated_at = datetime.now()
            await self._save_simulation(simulation)
            logger.info(f"Simulation terminée et marquée COMPLETED: {simulation.simulation_id}")
        elif simulation.status == SimulationStatus.COMPLETED:
             logger.info(f"Simulation {simulation.simulation_id} déjà marquée comme COMPLETED.")
        # Les cas CANCELLED et FAILED sont déjà loggés dans la boucle.


    async def _process_task_result_global(self, result_data: Dict[str, Any]):
        """Traiter le résultat d'une tâche de manière globale."""
        try:
            task_id_from_result = result_data.get('task_id')
            if not task_id_from_result:
                logger.error(f"Résultat de tâche reçu sans task_id: {result_data}")
                return

            # Extraire le simulation_id du task_id (ex: "sim_id_batch_0")
            parts = task_id_from_result.split('_batch_')
            if len(parts) < 2: # Gère aussi le cas où _batch_ n'est pas dans le nom
                 # Tenter d'extraire le simulation_id d'un champ dédié si disponible
                actual_simulation_id = result_data.get('simulation_id')
                if not actual_simulation_id:
                    logger.error(f"Impossible d'extraire simulation_id de task_id: {task_id_from_result}")
                    return
            else:
                actual_simulation_id = parts[0]


            # Vérifier si cette simulation est gérée par ce manager
            if actual_simulation_id not in self.simulations:
                logger.warning(
                    f"Résultat reçu pour une simulation inconnue ou non gérée: {actual_simulation_id}. "
                    f"Task ID: {task_id_from_result}. Ce message peut être normal si la simulation a été supprimée ou annulée."
                )
                # On ne traite pas plus loin si la simulation n'est plus activement gérée.
                # Cela évite des erreurs si une simulation est annulée et ses résultats arrivent tardivement.
                return

            # Mettre à jour les informations de la simulation concernée si nécessaire
            # Par exemple, si le résultat contient des informations sur l'exploitabilité actuelle
            target_simulation = self.simulations.get(actual_simulation_id)
            if target_simulation and result_data.get('success'):
                task_result_payload = result_data.get('result_data', {})
                if 'exploitability' in task_result_payload:
                    target_simulation.current_exploitability = task_result_payload['exploitability']
                # Note: iterations_completed est mis à jour par _monitor_simulation_progress
                target_simulation.updated_at = datetime.now()
                # Pas besoin de sauvegarder ici, _monitor_simulation_progress le fait.

            # Sauvegarder le résultat partiel
            result_file_name = f"{actual_simulation_id}_task_{task_id_from_result}.json"
            result_file_path = os.path.join(self.storage_path, result_file_name)
            
            async with aiofiles.open(result_file_path, "w") as f:
                await f.write(json.dumps(result_data, indent=2))

            logger.info(f"Résultat de tâche traité et sauvegardé: {result_file_name} pour simulation {actual_simulation_id}")

        except Exception as e:
            logger.error(f"Erreur lors du traitement du résultat de tâche global: {e}", exc_info=True)

    async def _count_completed_tasks(self, simulation_id: str) -> int:
        """Compter le nombre de tâches terminées pour une simulation."""
        import glob

        pattern = f"{self.storage_path}/{simulation_id}_task_*.json"
        return len(glob.glob(pattern))

    async def _aggregate_results(self, simulation: Simulation):
        """Agréger les résultats partiels en résultat final."""
        import glob

        pattern = f"{self.storage_path}/{simulation.simulation_id}_task_*.json"
        result_files = glob.glob(pattern)

        # Agréger les stratégies et calculer la performance finale
        aggregated_strategy = {}
        total_iterations = 0
        final_exploitability = 0.0

        for result_file in result_files:
            async with aiofiles.open(result_file, "r") as f:
                content = await f.read()
                task_result = json.loads(content)

                if task_result.get("success") and task_result.get("result_data"):
                    data = task_result["result_data"]

                    # Fusionner les stratégies (logique simplifiée)
                    if "strategy" in data:
                        for key, value in data["strategy"].items():
                            if key not in aggregated_strategy:
                                aggregated_strategy[key] = []
                            aggregated_strategy[key].append(value)

                    total_iterations += data.get(
                        "iterations_completed", 0
                    )
                    final_exploitability = max(
                        final_exploitability,
                        data.get("exploitability", 0.0)
                    )

        # Moyenner les stratégies
        final_strategy = {}
        for key, values in aggregated_strategy.items():
            if values:
                final_strategy[key] = sum(values) / len(values)

        # Calculer le temps de convergence
        convergence_time = (datetime.now() - simulation.created_at).total_seconds()

        # Créer l'objet résultat
        results = SimulationResults(
            simulation_id=simulation.simulation_id,
            final_strategy=final_strategy,
            final_exploitability=final_exploitability,
            iterations_completed=total_iterations,
            convergence_time=convergence_time,
            metadata={
                "simulation_type": simulation.simulation_type,
                "game_config": simulation.game_config,
                "solver_config": simulation.solver_config,
                "num_tasks": len(result_files)
            }
        )

        self.results[simulation.simulation_id] = results
        await self._save_results(results)

        logger.info(
            f"Résultats agrégés pour la simulation {simulation.simulation_id}"
        )

    async def get_simulation_status(
        self, simulation_id: str
    ) -> Optional[Simulation]:
        """Obtenir le statut d'une simulation."""
        return self.simulations.get(simulation_id)

    async def get_simulation_results(
        self, simulation_id: str
    ) -> Optional[SimulationResults]:
        """Obtenir les résultats d'une simulation."""
        return self.results.get(simulation_id)

    async def list_simulations(
        self,
        status_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[Simulation]:
        """Lister les simulations avec filtres optionnels."""
        simulations = list(self.simulations.values())

        if status_filter:
            simulations = [
            s for s in simulations if s.status.value == status_filter
        ]

        if type_filter:
            simulations = [
                s for s in simulations if s.simulation_type == type_filter
            ]

        # Trier par date de création (plus récent en premier)
        simulations.sort(key=lambda s: s.created_at, reverse=True)

        return simulations[:limit]

    async def cancel_simulation(self, simulation_id: str) -> bool:
        """Annuler une simulation en cours."""
        simulation = self.simulations.get(simulation_id)
        if not simulation or simulation.status not in [
            SimulationStatus.PENDING, SimulationStatus.RUNNING
        ]:
            return False

        simulation.status = SimulationStatus.CANCELLED
        simulation.updated_at = datetime.now()
        await self._save_simulation(simulation)

        # Annuler la tâche en cours si elle existe
        if simulation_id in self.running_simulations:
            self.running_simulations[simulation_id].cancel()

        logger.info(f"Simulation annulée: {simulation_id}")
        return True

    def get_active_simulations(self) -> List[str]:
        """Obtenir la liste des simulations actives."""
        return [
            sim_id
            for sim_id, sim in self.simulations.items()
            if sim.status in [
                SimulationStatus.PENDING, SimulationStatus.RUNNING
            ]
        ]

    async def get_compute_nodes_status(self) -> List[Dict[str, Any]]:
        """Obtenir le statut des nœuds de calcul (simulation pour l'instant)."""
        # Pour l'instant, retourner des données simulées
        # Dans une vraie implémentation, ceci interrogerait les vrais nœuds
        return [
            {
                "node_id": "compute-node-1",
                "status": "active",
                "current_tasks": 2,
                "total_capacity": 4,
                "last_heartbeat": datetime.now().isoformat()
            },
            {
                "node_id": "compute-node-2",
                "status": "active",
                "current_tasks": 1,
                "total_capacity": 4,
                "last_heartbeat": datetime.now().isoformat()
            }
        ]

    async def _save_simulation(self, simulation: Simulation):
        """Sauvegarder une simulation sur disque."""
        file_path = f"{self.storage_path}/simulation_{simulation.simulation_id}.json"

        # Convertir en dictionnaire sérialisable
        data = asdict(simulation)
        data["status"] = simulation.status.value
        data["created_at"] = simulation.created_at.isoformat()
        data["updated_at"] = simulation.updated_at.isoformat()
        if simulation.estimated_completion_time:
            data["estimated_completion_time"] = (
                simulation.estimated_completion_time.isoformat()
            )

        async with aiofiles.open(file_path, "w") as f:
            await f.write(json.dumps(data, indent=2))

    async def _save_results(self, results: SimulationResults):
        """Sauvegarder les résultats d'une simulation."""
        file_path = f"{self.storage_path}/results_{results.simulation_id}.json"

        async with aiofiles.open(file_path, "w") as f:
            await f.write(json.dumps(asdict(results), indent=2))
