#!/bin/bash
# Script pour vérifier et corriger les fichiers frontend avant de démarrer l'application

set -e

echo "🔍 Vérification des fichiers frontend..."

FRONTEND_DIR="/Users/bastienjavaux/Desktop/AlphaBetaSolver/frontend"

# Vérifier que les fichiers existent et ne sont pas vides
check_file() {
    local file="$1"
    local filepath="$FRONTEND_DIR/$file"
    
    if [ ! -f "$filepath" ]; then
        echo "❌ Le fichier $file n'existe pas!"
        return 1
    fi
    
    if [ ! -s "$filepath" ]; then
        echo "❌ Le fichier $file est vide!"
        return 1
    fi
    
    echo "✅ Le fichier $file est valide ($(wc -c < "$filepath") octets)"
    return 0
}

# Vérifier tous les fichiers essentiels
FILES_TO_CHECK=("index.html" "styles.css" "api-gateway.js" "strategy-visualizer.js")
ALL_FILES_VALID=true

for file in "${FILES_TO_CHECK[@]}"; do
    if ! check_file "$file"; then
        ALL_FILES_VALID=false
    fi
done

# Vérifier que le CSS est correctement référencé dans le HTML
if ! grep -q "link.*stylesheet.*styles.css" "$FRONTEND_DIR/index.html"; then
    echo "❌ Le fichier CSS n'est pas correctement référencé dans index.html!"
    ALL_FILES_VALID=false
else
    echo "✅ Le CSS est correctement référencé dans index.html"
fi

if [ "$ALL_FILES_VALID" = true ]; then
    echo "✅ Tous les fichiers frontend sont valides!"
else
    echo "❌ Certains fichiers frontend sont invalides ou manquants."
    echo "⚠️ Veuillez résoudre les problèmes avant de démarrer l'application."
    exit 1
fi

# Vérifier la configuration Nginx
NGINX_CONF="/Users/bastienjavaux/Desktop/AlphaBetaSolver/nginx.conf"

if [ ! -f "$NGINX_CONF" ]; then
    echo "❌ Le fichier de configuration Nginx n'existe pas!"
    exit 1
fi

echo "🔍 Vérification de la configuration Nginx..."
if ! grep -q "text/css" "$NGINX_CONF"; then
    echo "⚠️ La configuration Nginx ne spécifie pas explicitement le type MIME pour CSS."
    echo "⚠️ Ajout de la configuration pour les fichiers CSS..."
    
    # Backup de l'original
    cp "$NGINX_CONF" "${NGINX_CONF}.backup"
    
    # Ajouter la configuration pour les fichiers CSS
    sed -i '' '/location \/ {/a\\
        # Special configuration for CSS files to ensure proper MIME type\
        location ~* \\.css$ {\
            add_header Content-Type text/css;\
            expires 1y;\
            add_header Cache-Control "public, immutable";\
            access_log off;\
        }\
    ' "$NGINX_CONF"
    
    echo "✅ Configuration Nginx mise à jour pour les fichiers CSS"
fi

echo "✅ Vérification terminée. Tout est prêt pour démarrer l'application!"
