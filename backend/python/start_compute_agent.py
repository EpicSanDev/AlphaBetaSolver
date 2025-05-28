#!/usr/bin/env python3
"""
Script de démarrage pour un compute node.
Configure le Python path et démarre l'agent de calcul.
"""
import sys
import os

# Ajouter le répertoire parent au Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Maintenant importer et démarrer l'agent
if __name__ == "__main__":
    import asyncio
    
    async def main_agent(queue_name: str):
        from compute_node.agent import ComputeAgent
        
        # L'agent utilisera automatiquement les variables d'environnement pour RabbitMQ URL
        # si non spécifié explicitement lors de l'instanciation.
        agent = ComputeAgent(
            queue_name=queue_name,
            result_queue="computation_results", # La file des résultats reste la même
        )
        
        print(f"🚀 Démarrage de l'agent de calcul pour la file : {queue_name}...")
        try:
            await agent.start_consuming()
        except KeyboardInterrupt:
            print(f"Arrêt de l'agent pour la file {queue_name} demandé.")
        finally:
            await agent.stop()

    if __name__ == "__main__":
        import argparse
        parser = argparse.ArgumentParser(description="Démarre un agent de calcul pour une file RabbitMQ spécifique.")
        parser.add_argument(
            "--queue",
            type=str,
            required=True,
            choices=["preflop_tasks", "postflop_tasks"],
            help="Le nom de la file de tâches à écouter (preflop_tasks ou postflop_tasks)."
        )
        args = parser.parse_args()

        asyncio.run(main_agent(args.queue))
