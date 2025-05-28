#!/usr/bin/env python3
"""
Script de démarrage pour le master node.
Configure le Python path et démarre l'application.
"""
import sys
import os

# Ajouter le répertoire parent au Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Maintenant importer et démarrer l'application
if __name__ == "__main__":
    from master_node.main import main
    main()
