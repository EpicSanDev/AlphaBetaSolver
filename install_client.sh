#!/bin/bash
# Script d'installation automatique du client de calcul AlphaBetaSolver
# Ce script installe et démarre le client de calcul pour contribuer au cluster

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

# Vérifier si Python est installé (version 3.7+)
check_python() {
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &>/dev/null && [[ $(python --version 2>&1) == *"Python 3"* ]]; then
        PYTHON_CMD="python"
    else
        log_error "Python 3 n'est pas installé. Veuillez installer Python 3.7 ou supérieur."
        exit 1
    fi

    # Vérifier la version de Python
    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if (( $(echo "$PYTHON_VERSION < 3.7" | bc -l) )); then
        log_error "Python $PYTHON_VERSION détecté. Ce script nécessite Python 3.7 ou supérieur."
        exit 1
    fi

    log_info "Python $PYTHON_VERSION détecté."
}

# Créer un environnement virtuel
create_venv() {
    if [ "$USE_VENV" = true ]; then
        log_info "Création de l'environnement virtuel..."
        if [ -d ".venv" ]; then
            log_warn "L'environnement virtuel existe déjà."
        else
            $PYTHON_CMD -m venv .venv
            if [ $? -ne 0 ]; then
                log_error "Échec lors de la création de l'environnement virtuel."
                exit 1
            fi
            log_info "Environnement virtuel créé avec succès."
        fi

        # Activer l'environnement virtuel
        if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
            source .venv/Scripts/activate
        else
            source .venv/bin/activate
        fi
        
        if [ $? -ne 0 ]; then
            log_error "Échec lors de l'activation de l'environnement virtuel."
            exit 1
        fi
        log_info "Environnement virtuel activé."
        PYTHON_CMD="python"
    fi
}

# Installer les dépendances
install_dependencies() {
    log_info "Installation des dépendances..."
    $PYTHON_CMD -m pip install --upgrade pip
    
    # Installer les dépendances via compute_client.py
    $PYTHON_CMD compute_client.py --install
    
    if [ $? -ne 0 ]; then
        log_error "Échec lors de l'installation des dépendances."
        exit 1
    fi
    log_info "Dépendances installées avec succès."
}

# Lancer le client
start_client() {
    log_info "Démarrage du client de calcul..."
    
    # Construire la commande avec les options
    CMD="$PYTHON_CMD compute_client.py"
    
    if [ -n "$MASTER_URL" ]; then
        CMD="$CMD --master-url $MASTER_URL"
    fi
    
    if [ -n "$NODE_ID" ]; then
        CMD="$CMD --node-id $NODE_ID"
    fi
    
    if [ -n "$MAX_TASKS" ]; then
        CMD="$CMD --max-tasks $MAX_TASKS"
    fi
    
    if [ "$VERBOSE" = true ]; then
        CMD="$CMD --verbose"
    fi
    
    log_info "Exécution de: $CMD"
    
    # Exécuter la commande
    if [ "$DETACHED" = true ]; then
        nohup $CMD > client.log 2>&1 &
        CLIENT_PID=$!
        log_info "Client démarré en arrière-plan (PID: $CLIENT_PID)"
        log_info "Les logs sont disponibles dans client.log"
    else
        $CMD
    fi
}

# Afficher l'aide
show_help() {
    echo "Script d'installation et de démarrage du client de calcul AlphaBetaSolver"
    echo ""
    echo "Options:"
    echo "  -h, --help                   Afficher cette aide"
    echo "  -m, --master-url URL         URL du nœud maître (défaut: http://localhost:8000)"
    echo "  -i, --node-id ID             ID unique du nœud (généré automatiquement si non spécifié)"
    echo "  -t, --max-tasks NOMBRE       Nombre maximum de tâches simultanées"
    echo "  -v, --verbose                Mode verbeux"
    echo "  -d, --detached               Démarrer le client en arrière-plan"
    echo "  --no-venv                    Ne pas utiliser d'environnement virtuel"
    echo "  --install-only               Installer les dépendances sans démarrer le client"
    echo ""
    echo "Exemple:"
    echo "  ./install_client.sh --master-url http://master.example.com:8000 --max-tasks 8 --detached"
}

# Traiter les arguments
MASTER_URL=""
NODE_ID=""
MAX_TASKS=""
VERBOSE=false
DETACHED=false
USE_VENV=true
INSTALL_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -m|--master-url)
            MASTER_URL="$2"
            shift 2
            ;;
        -i|--node-id)
            NODE_ID="$2"
            shift 2
            ;;
        -t|--max-tasks)
            MAX_TASKS="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -d|--detached)
            DETACHED=true
            shift
            ;;
        --no-venv)
            USE_VENV=false
            shift
            ;;
        --install-only)
            INSTALL_ONLY=true
            shift
            ;;
        *)
            log_error "Option inconnue: $1"
            show_help
            exit 1
            ;;
    esac
done

# Programme principal
log_info "Début de l'installation du client de calcul AlphaBetaSolver"

# Vérifier Python
check_python

# Créer et activer l'environnement virtuel si nécessaire
create_venv

# Installer les dépendances
install_dependencies

if [ "$INSTALL_ONLY" = true ]; then
    log_info "Installation terminée. Le client n'a pas été démarré (--install-only)."
    exit 0
fi

# Lancer le client
start_client

log_info "Script terminé."
