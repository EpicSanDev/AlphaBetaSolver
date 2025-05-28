#!/bin/bash
# Script de diagnostic pour le client de calcul
# Ce script teste la communication avec le serveur maître et aide à déboguer les problèmes

# Couleurs pour les messages
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Récupérer les paramètres
MASTER_URL=${1:-"http://localhost:8000"}
log_info "URL du serveur maître: $MASTER_URL"

# Vérifier si curl est installé
if ! command -v curl &> /dev/null; then
    log_error "curl n'est pas installé. Veuillez l'installer pour exécuter ce script."
    exit 1
fi

# Vérifier si jq est installé
if ! command -v jq &> /dev/null; then
    log_warn "jq n'est pas installé. L'affichage des résultats JSON sera limité."
    JQ_AVAILABLE=false
else
    JQ_AVAILABLE=true
fi

# Créer un ID de nœud pour les tests
TEST_NODE_ID="test-node-$(date +%s)"
log_info "ID de nœud de test: $TEST_NODE_ID"

# Tester la connexion au serveur
log_info "Test de connexion au serveur maître..."
if curl -s -o /dev/null -w "%{http_code}" "$MASTER_URL" | grep -q "200\|301\|302\|307\|308"; then
    log_info "Connexion au serveur réussie"
else
    log_error "Impossible de se connecter au serveur maître. Vérifiez l'URL et que le serveur est en cours d'exécution."
    exit 1
fi

# Enregistrer un nœud de test
log_info "Enregistrement d'un nœud de test..."
REGISTRATION_DATA='{
    "node_id": "'$TEST_NODE_ID'",
    "platform": "Test",
    "architecture": "Test",
    "cpu_count": 4,
    "memory_total": 8589934592,
    "python_version": "3.8.0",
    "max_concurrent_tasks": 2,
    "status": "available",
    "current_tasks": 0,
    "registration_time": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
}'

REGISTRATION_RESPONSE=$(curl -s -X POST "$MASTER_URL/api/v1/compute-nodes/register" \
    -H "Content-Type: application/json" \
    -d "$REGISTRATION_DATA")

log_debug "Réponse d'enregistrement: $REGISTRATION_RESPONSE"
if [[ "$REGISTRATION_RESPONSE" == *"success"* ]]; then
    log_info "Enregistrement réussi"
else
    log_warn "Enregistrement potentiellement échoué, vérifiez la réponse"
fi

# Demander une tâche
log_info "Demande d'une tâche au serveur maître..."
TASK_RESPONSE=$(curl -s "$MASTER_URL/api/v1/tasks/next?node_id=$TEST_NODE_ID")
log_debug "Réponse de tâche brute: $TASK_RESPONSE"

# Analyser la réponse
if [[ -z "$TASK_RESPONSE" ]]; then
    log_info "Aucune tâche disponible (réponse vide)"
elif [[ "$TASK_RESPONSE" == "null" ]]; then
    log_info "Aucune tâche disponible (null)"
else
    log_info "Tâche reçue, analyse..."
    
    # Afficher avec jq si disponible
    if [ "$JQ_AVAILABLE" = true ]; then
        echo "$TASK_RESPONSE" | jq '.'
        
        # Vérifier la présence d'un ID de tâche
        if echo "$TASK_RESPONSE" | jq -e '.task_id' > /dev/null 2>&1; then
            log_info "Tâche avec ID trouvée: $(echo "$TASK_RESPONSE" | jq -r '.task_id')"
        elif echo "$TASK_RESPONSE" | jq -e '.[0].task_id' > /dev/null 2>&1; then
            log_info "Tâche dans un tableau avec ID trouvée: $(echo "$TASK_RESPONSE" | jq -r '.[0].task_id')"
        elif echo "$TASK_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
            log_info "Tâche avec champ 'id' au lieu de 'task_id' trouvée: $(echo "$TASK_RESPONSE" | jq -r '.id')"
            log_warn "Le client s'attend à un champ 'task_id', pas 'id'"
        else
            log_error "Aucun ID de tâche trouvé dans la réponse"
        fi
    else
        # Affichage basique
        echo "$TASK_RESPONSE"
        if [[ "$TASK_RESPONSE" == *"task_id"* ]]; then
            log_info "Le champ task_id semble être présent"
        elif [[ "$TASK_RESPONSE" == *"\"id\""* ]]; then
            log_warn "Le champ 'id' est présent au lieu de 'task_id'"
        else
            log_error "Aucun champ d'ID trouvé"
        fi
    fi
fi

# Tester un envoi de résultat
log_info "Test d'envoi de résultat de tâche..."
TASK_RESULT='{
    "task_id": "test-task-001",
    "node_id": "'$TEST_NODE_ID'",
    "status": "completed",
    "result": {
        "test": true,
        "message": "Résultat de test"
    },
    "error": null,
    "completed_at": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
}'

RESULT_RESPONSE=$(curl -s -X POST "$MASTER_URL/api/v1/tasks/results" \
    -H "Content-Type: application/json" \
    -d "$TASK_RESULT" \
    -w "%{http_code}")

log_debug "Réponse d'envoi de résultat: $RESULT_RESPONSE"
if [[ "$RESULT_RESPONSE" == *"200"* ]]; then
    log_info "Envoi de résultat accepté par le serveur"
elif [[ "$RESULT_RESPONSE" == *"422"* ]]; then
    log_error "Erreur 422: Le serveur rejette le format de résultat"
else
    log_warn "Réponse inattendue lors de l'envoi du résultat: $RESULT_RESPONSE"
fi

# Désenregistrer le nœud de test
log_info "Désenregistrement du nœud de test..."
UNREGISTER_RESPONSE=$(curl -s -X DELETE "$MASTER_URL/api/v1/compute-nodes/$TEST_NODE_ID")
log_debug "Réponse de désenregistrement: $UNREGISTER_RESPONSE"

log_info "Diagnostic terminé"
