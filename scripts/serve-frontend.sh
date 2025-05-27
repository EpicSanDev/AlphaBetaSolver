#!/bin/bash
# Script pour servir directement le frontend sans Docker pour le débogage

# Vérifie si Python est disponible
if command -v python3 &>/dev/null; then
  PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
  PYTHON_CMD="python"
else
  echo "Python n'est pas installé. Installation nécessaire pour servir les fichiers."
  exit 1
fi

# Chemin vers le dossier frontend
FRONTEND_DIR="/Users/bastienjavaux/Desktop/AlphaBetaSolver/frontend"

# Affiche un message pour le démarrage
echo "🚀 Démarrage du serveur frontend local sur http://localhost:8080"
echo "📁 Serving files from: $FRONTEND_DIR"
echo "📝 Appuyez sur Ctrl+C pour arrêter le serveur"
echo "---------------------------------------------------"

# Démarrer un serveur HTTP simple avec Python
cd "$FRONTEND_DIR" && $PYTHON_CMD -m http.server 8080
