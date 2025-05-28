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
    
    async def main():
        from compute_node.agent import ComputeAgent
        
        # L'agent utilisera automatiquement les variables d'environnement
        agent = ComputeAgent(
            queue_name="preflop_tasks",
            result_queue="computation_results",
        )
        
        print("🚀 Démarrage de l'agent de calcul...")
        await agent.start_consuming()
    
    asyncio.run(main())
