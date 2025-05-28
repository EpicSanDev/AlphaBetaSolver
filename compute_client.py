#!/usr/bin/env python3
"""
Client de calcul distribué pour le GTO Poker Solver
Ce script permet à n'importe qui de connecter son ordinateur au cluster
pour contribuer à la puissance de calcul.
"""

import asyncio
import aiohttp
import json
import uuid
import psutil
import platform
import logging
import signal
import sys
import subprocess
import os
from datetime import datetime
from typing import Dict, Optional, Any
import argparse

# Configuration par défaut
DEFAULT_MASTER_URL = "http://localhost:8000"
DEFAULT_RABBITMQ_HOST = "localhost"
DEFAULT_RABBITMQ_PORT = 5672
DEFAULT_RABBITMQ_USER = "gto_user"
DEFAULT_RABBITMQ_PASSWORD = "gto_password"

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComputeClient:
    """Client de calcul distribué."""
    
    def __init__(self, master_url: str, node_id: Optional[str] = None, max_concurrent_tasks: int = None, debug_mode: bool = False, dump_tasks: bool = False):
        self.master_url = master_url.rstrip('/')
        self.node_id = node_id or f"compute-client-{str(uuid.uuid4())[:8]}"
        self.max_concurrent_tasks = max_concurrent_tasks or min(psutil.cpu_count(), 4)
        self.running = False
        self.current_tasks = {}
        self.session = None
        self.debug_mode = debug_mode
        self.dump_tasks = dump_tasks
        
        # Configurer le niveau de log si debug_mode est activé
        if debug_mode:
            logger.setLevel(logging.DEBUG)
            logger.debug("Mode debug activé")
            
        # Créer un dossier pour sauvegarder les tâches si dump_tasks est activé
        if dump_tasks:
            os.makedirs("task_dumps", exist_ok=True)
            logger.info("Mode dump des tâches activé, les tâches seront sauvegardées dans le dossier 'task_dumps'")
        
        # Informations système
        self.system_info = self._get_system_info()
        
        logger.info(f"Client de calcul initialisé: {self.node_id}")
        logger.info(f"Tâches simultanées max: {self.max_concurrent_tasks}")
        logger.info(f"Système: {self.system_info['platform']} {self.system_info['architecture']}")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Obtenir les informations système."""
        return {
            "node_id": self.node_id,
            "platform": platform.system(),
            "architecture": platform.machine(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "python_version": platform.python_version(),
            "max_concurrent_tasks": self.max_concurrent_tasks
        }
    
    async def start(self):
        """Démarrer le client de calcul."""
        self.running = True
        
        # Créer une session HTTP persistante
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300)  # 5 minutes
        )
        
        try:
            # S'enregistrer auprès du maître
            await self._register_with_master()
            
            # Démarrer les tâches de service
            tasks = [
                asyncio.create_task(self._heartbeat_loop()),
                asyncio.create_task(self._task_consumer_loop()),
                asyncio.create_task(self._system_monitor_loop())
            ]
            
            # Attendre que toutes les tâches se terminent
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage: {e}")
        finally:
            await self._cleanup()
    
    async def stop(self):
        """Arrêter le client de calcul."""
        logger.info("Arrêt du client de calcul...")
        self.running = False
        
        # Annuler toutes les tâches en cours
        for task_id, task in self.current_tasks.items():
            logger.info(f"Annulation de la tâche: {task_id}")
            task.cancel()
        
        # Se désenregistrer du maître
        if self.session:
            try:
                await self._unregister_from_master()
            except Exception as e:
                logger.warning(f"Erreur lors du désenregistrement: {e}")
    
    async def _register_with_master(self):
        """S'enregistrer auprès du nœud maître."""
        registration_data = {
            **self.system_info,
            "status": "available",
            "current_tasks": 0,
            "registration_time": datetime.now().isoformat()
        }
        
        try:
            async with self.session.post(
                f"{self.master_url}/api/v1/compute-nodes/register",
                json=registration_data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Enregistrement réussi: {result.get('message', 'OK')}")
                else:
                    logger.error(f"Erreur d'enregistrement: {response.status}")
                    
        except Exception as e:
            logger.error(f"Impossible de s'enregistrer: {e}")
            raise
    
    async def _unregister_from_master(self):
        """Se désenregistrer du nœud maître."""
        try:
            async with self.session.delete(
                f"{self.master_url}/api/v1/compute-nodes/{self.node_id}"
            ) as response:
                if response.status == 200:
                    logger.info("Désenregistrement réussi")
                else:
                    logger.warning(f"Erreur de désenregistrement: {response.status}")
                    
        except Exception as e:
            logger.warning(f"Erreur lors du désenregistrement: {e}")
    
    async def _heartbeat_loop(self):
        """Boucle de heartbeat pour maintenir la connexion."""
        while self.running:
            try:
                heartbeat_data = {
                    "node_id": self.node_id,
                    "status": "available" if len(self.current_tasks) < self.max_concurrent_tasks else "busy",
                    "current_tasks": len(self.current_tasks),
                    "total_capacity": self.max_concurrent_tasks,
                    "cpu_usage": psutil.cpu_percent(),
                    "memory_usage": psutil.virtual_memory().percent,
                    "timestamp": datetime.now().isoformat()
                }
                
                async with self.session.post(
                    f"{self.master_url}/api/v1/compute-nodes/{self.node_id}/heartbeat",
                    json=heartbeat_data
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Heartbeat failed: {response.status}")
                
                await asyncio.sleep(30)  # Heartbeat toutes les 30 secondes
                
            except Exception as e:
                logger.error(f"Erreur de heartbeat: {e}")
                await asyncio.sleep(30)
    
    async def _task_consumer_loop(self):
        """Boucle de consommation des tâches."""
        while self.running:
            try:
                # Vérifier si on peut prendre plus de tâches
                if len(self.current_tasks) >= self.max_concurrent_tasks:
                    await asyncio.sleep(5)
                    continue
                
                # Demander une nouvelle tâche
                async with self.session.get(
                    f"{self.master_url}/api/v1/tasks/next",
                    params={"node_id": self.node_id}
                ) as response:
                    if response.status == 200:
                        try:
                            task_data = await response.json()
                            # Log the raw task data for debugging
                            logger.debug(f"Tâche reçue du serveur: {task_data}")
                            
                            # Sauvegarder la tâche si dump_tasks est activé
                            if self.dump_tasks:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                dump_file = f"task_dumps/task_{timestamp}.json"
                                with open(dump_file, 'w') as f:
                                    json.dump(task_data, f, indent=2)
                                logger.debug(f"Tâche sauvegardée dans {dump_file}")
                            
                            # Si les données sont une liste, prendre le premier élément
                            if isinstance(task_data, list) and task_data:
                                logger.info("Tâche reçue sous forme de liste, extraction du premier élément")
                                task_data = task_data[0]
                            
                            # Si task_data est un dictionnaire mais avec une structure différente
                            if isinstance(task_data, dict) and "id" in task_data and not "task_id" in task_data:
                                logger.info("Format de tâche non standard détecté, adaptation du format")
                                task_data["task_id"] = task_data.pop("id")
                            
                            # Vérifier que les données de tâche sont valides
                            if not task_data or not task_data.get("task_id"):
                                logger.warning(f"Tâche reçue sans ID valide, ignorée: {task_data}")
                                await asyncio.sleep(5)
                                continue
                                
                            await self._process_task(task_data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Erreur de décodage JSON lors de la récupération de tâche: {e}")
                            # Log the raw response
                            raw_text = await response.text()
                            logger.debug(f"Réponse brute reçue: {raw_text[:200]}")
                            await asyncio.sleep(5)
                    elif response.status == 204:
                        # Pas de tâches disponibles
                        await asyncio.sleep(10)
                    else:
                        logger.warning(f"Erreur lors de la récupération de tâche: {response.status}")
                        await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Erreur dans la boucle de consommation: {e}")
                await asyncio.sleep(10)
    
    async def _process_task(self, task_data: Dict[str, Any]):
        """Traiter une tâche de calcul."""
        task_id = task_data.get("task_id")
        task_type = task_data.get("task_type")
        
        if not task_id:
            logger.warning("Tentative de traitement d'une tâche sans ID, ignorée")
            return
            
        logger.info(f"Démarrage de la tâche: {task_id} (type: {task_type})")
        
        # Créer une tâche asyncio pour le traitement
        task = asyncio.create_task(self._execute_task(task_data))
        self.current_tasks[task_id] = task
        
        try:
            result = await task
            await self._send_task_result(task_id, result, "completed")
            logger.info(f"Tâche terminée: {task_id}")
            
        except asyncio.CancelledError:
            await self._send_task_result(task_id, None, "cancelled")
            logger.info(f"Tâche annulée: {task_id}")
            
        except Exception as e:
            await self._send_task_result(task_id, None, "failed", str(e))
            logger.error(f"Erreur dans la tâche {task_id}: {e}")
        
        finally:
            self.current_tasks.pop(task_id, None)
    
    async def _execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Exécuter une tâche de calcul."""
        task_id = task_data.get("task_id", "unknown")
        task_type = task_data.get("task_type")
        params = task_data.get("params", {})
        
        # Mode test pour vérifier si le client fonctionne sans binaire
        test_mode = os.environ.get("GTO_CLIENT_TEST_MODE", "").lower() in ["1", "true", "yes"]
        if test_mode:
            logger.info(f"Mode test activé, simulation de calcul pour la tâche {task_id}")
            await asyncio.sleep(2)  # Simuler un temps de calcul
            return {
                "status": "success",
                "task_id": task_id,
                "result": {
                    "simulation": True,
                    "message": "Résultat de test"
                }
            }
            
        # Vérifier si le binaire de calcul existe
        backend_binary = "/app/backend/build/src/PokerSolver"
        if not os.path.exists(backend_binary):
            # Essayer un chemin local
            backend_binary = "./backend/build/src/PokerSolver"
            if not os.path.exists(backend_binary):
                raise Exception(f"Binaire de calcul non trouvé. Recherché dans: /app/backend/build/src/PokerSolver et ./backend/build/src/PokerSolver")
        
        # Préparer les paramètres de la tâche
        task_params = {
            "task_type": task_type,
            "params": params,
            "output_format": "json"
        }
        
        # Exécuter le calcul dans un sous-processus
        cmd = [backend_binary, json.dumps(task_params)]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Erreur de calcul inconnue"
            raise Exception(f"Erreur de calcul: {error_msg}")
        
        # Parser le résultat JSON
        try:
            result_text = stdout.decode().strip()
            if not result_text:
                raise Exception("Résultat vide retourné par le binaire")
                
            result = json.loads(result_text)
            return result
        except json.JSONDecodeError as e:
            # Log the raw output for debugging
            logger.error(f"JSON invalide reçu du binaire: '{stdout.decode()[:100]}...'")
            raise Exception(f"Erreur de parsing du résultat: {e}")
    
    async def _send_task_result(self, task_id: str, result: Optional[Dict], status: str, error: Optional[str] = None):
        """Envoyer le résultat d'une tâche au maître."""
        if not task_id:
            logger.warning("Tentative d'envoi de résultat pour une tâche sans ID, ignorée")
            return
            
        # Format API v1 attendu par le serveur:
        # - task_id: str (obligatoire)
        # - status: str (obligatoire): 'completed', 'failed', 'error', 'cancelled'
        # - results: dict (obligatoire): les résultats réels de la tâche
        # - execution_time: float (optionnel): temps d'exécution en millisecondes
        # - memory_usage: float (optionnel): utilisation mémoire en MB
        # - error_message: str (optionnel): message d'erreur si statut error/failed
        
        # Collecter les métriques d'exécution
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / (1024 * 1024)  # MB
        
        result_data = {
            "task_id": task_id,
            "status": status,
            "results": result or {},  # Champ renommé de "result" à "results"
            "execution_time": 0,  # Valeur à remplir si disponible
            "memory_usage": memory_usage
        }
        
        # Ajouter le message d'erreur si présent
        if error:
            result_data["error_message"] = error
        
        if self.dump_tasks:
            # Sauvegarder les données de la tâche pour debugging
            dump_file = f"task_result_{task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(dump_file, 'w') as f:
                json.dump(result_data, f, indent=2)
            logger.info(f"Données de résultat sauvegardées dans {dump_file}")
        
        try:
            async with self.session.post(
                f"{self.master_url}/api/v1/tasks/results",
                json=result_data
            ) as response:
                if response.status == 422:
                    # Log détaillé en cas d'erreur de validation
                    error_data = await response.json()
                    logger.error(f"Erreur de validation (422): {error_data}")
                    if self.debug_mode:
                        logger.debug(f"Données envoyées: {result_data}")
                elif response.status != 200:
                    response_text = await response.text()
                    logger.warning(f"Erreur lors de l'envoi du résultat: {response.status} - {response_text}")
                else:
                    logger.info(f"Résultat de la tâche {task_id} envoyé avec succès (statut: {status})")
                    
        except Exception as e:
            logger.error(f"Impossible d'envoyer le résultat: {e}")
            if self.debug_mode:
                logger.exception("Détails de l'erreur:")
    
    async def _system_monitor_loop(self):
        """Surveillance système pour détecter les surcharges."""
        while self.running:
            try:
                cpu_usage = psutil.cpu_percent(interval=1)
                memory_usage = psutil.virtual_memory().percent
                
                # Si le système est surchargé, réduire temporairement la charge
                if cpu_usage > 90 or memory_usage > 90:
                    logger.warning(f"Système surchargé (CPU: {cpu_usage}%, RAM: {memory_usage}%)")
                    # Annuler une tâche si nécessaire
                    if self.current_tasks:
                        oldest_task_id = next(iter(self.current_tasks))
                        logger.info(f"Annulation de la tâche {oldest_task_id} pour réduire la charge")
                        self.current_tasks[oldest_task_id].cancel()
                
                await asyncio.sleep(60)  # Vérifier toutes les minutes
                
            except Exception as e:
                logger.error(f"Erreur de surveillance système: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup(self):
        """Nettoyer les ressources."""
        if self.session:
            await self.session.close()


def signal_handler(signum, frame):
    """Gestionnaire de signaux pour arrêt propre."""
    logger.info(f"Signal {signum} reçu, arrêt en cours...")
    sys.exit(0)


def install_requirements():
    """Installer les dépendances Python requises."""
    requirements = [
        "aiohttp>=3.8.0",
        "psutil>=5.8.0",
        "asyncio-mqtt>=0.11.0"
    ]
    
    for requirement in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", requirement])
            logger.info(f"Installé: {requirement}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Erreur d'installation de {requirement}: {e}")
            return False
    
    return True


async def main():
    """Fonction principale."""
    parser = argparse.ArgumentParser(description="Client de calcul distribué GTO Poker Solver")
    parser.add_argument("--master-url", default=DEFAULT_MASTER_URL, help="URL du nœud maître")
    parser.add_argument("--node-id", help="ID unique du nœud (généré automatiquement si non spécifié)")
    parser.add_argument("--max-tasks", type=int, help="Nombre maximum de tâches simultanées")
    parser.add_argument("--install", action="store_true", help="Installer les dépendances")
    parser.add_argument("--verbose", "-v", action="store_true", help="Mode verbeux")
    parser.add_argument("--debug", "-d", action="store_true", help="Mode debug (logs détaillés)")
    parser.add_argument("--dump-tasks", action="store_true", help="Enregistrer les tâches reçues dans un fichier JSON")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.install:
        logger.info("Installation des dépendances...")
        if install_requirements():
            logger.info("Installation terminée avec succès!")
        else:
            logger.error("Erreur lors de l'installation")
            sys.exit(1)
        return
    
    # Installer les gestionnaires de signaux
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Créer et démarrer le client
    client = ComputeClient(
        master_url=args.master_url,
        node_id=args.node_id,
        max_concurrent_tasks=args.max_tasks,
        debug_mode=args.debug,
        dump_tasks=args.dump_tasks
    )
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
    finally:
        await client.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Programme interrompu")
    except Exception as e:
        logger.error(f"Erreur: {e}")
        sys.exit(1)
