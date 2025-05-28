#!/bin/bash
# Script de démarrage du client en mode test
# Ce mode ne nécessite pas le binaire PokerSolver et retourne des données simulées

# Couleurs pour les messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Fonction pour afficher les messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Afficher l'aide
show_help() {
    echo "Script de démarrage du client en mode test"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help                 Afficher cette aide"
    echo "  -u, --url URL              URL du serveur maître (défaut: http://localhost:8000)"
    echo "  -t, --tasks NUMBER         Nombre maximum de tâches simultanées (défaut: 4)"
    echo "  -f, --foreground           Exécuter en premier plan (par défaut: arrière-plan)"
    echo "  -d, --debug                Activer le mode debug (logs détaillés)"
    echo "  --dump-tasks               Sauvegarder les tâches reçues dans des fichiers JSON"
    echo "  --run-diagnostic           Exécuter le diagnostic avant de démarrer le client"
    echo ""
    echo "Exemple:"
    echo "  $0 --url http://master.example.com:8000 --tasks 8 --debug"
}

# Paramètres par défaut
MASTER_URL="http://localhost:8000"
MAX_TASKS=4
FOREGROUND=false
DEBUG=false
DUMP_TASKS=false
RUN_DIAGNOSTIC=false

# Traiter les arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -u|--url)
            MASTER_URL="$2"
            shift 2
            ;;
        -t|--tasks)
            MAX_TASKS="$2"
            shift 2
            ;;
        -f|--foreground)
            FOREGROUND=true
            shift
            ;;
        -d|--debug)
            DEBUG=true
            shift
            ;;
        --dump-tasks)
            DUMP_TASKS=true
            shift
            ;;
        --run-diagnostic)
            RUN_DIAGNOSTIC=true
            shift
            ;;
        *)
            log_error "Option inconnue: $1"
            show_help
            exit 1
            ;;
    esac
done

# Définir la variable d'environnement pour le mode test
export GTO_CLIENT_TEST_MODE=true

# Afficher les paramètres
log_info "Démarrage du client en mode TEST"
log_info "URL du maître: $MASTER_URL"
log_info "Tâches max: $MAX_TASKS"
log_warn "Ce mode simule le calcul et ne nécessite pas le binaire PokerSolver"

# Récupérer le chemin du répertoire du script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Exécuter le diagnostic si demandé
if [ "$RUN_DIAGNOSTIC" = true ]; then
    log_info "Exécution du diagnostic..."
    "$SCRIPT_DIR/diagnostic_client.sh" "$MASTER_URL"
    log_info "Diagnostic terminé, démarrage du client..."
fi

# Activer l'environnement virtuel si présent
if [ -d "$SCRIPT_DIR/.venv" ]; then
    log_info "Activation de l'environnement virtuel"
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Construire la commande
CMD="python $SCRIPT_DIR/compute_client.py --master-url $MASTER_URL --max-tasks $MAX_TASKS"

if [ "$DEBUG" = true ]; then
    CMD="$CMD --debug"
fi

if [ "$DUMP_TASKS" = true ]; then
    CMD="$CMD --dump-tasks"
fi

# Exécuter le client
log_info "Exécution de: $CMD"

if [ "$FOREGROUND" = true ]; then
    log_info "Exécution en premier plan"
    $CMD
else
    log_info "Exécution en arrière-plan"
    nohup $CMD > client_test.log 2>&1 &
    CLIENT_PID=$!
    log_info "Client démarré en mode test (PID: $CLIENT_PID)"
    log_info "Les logs sont disponibles dans client_test.log"
fi
