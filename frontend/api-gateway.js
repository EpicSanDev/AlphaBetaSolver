// Frontend API Gateway
// Ce fichier centralise toutes les requêtes API du frontend

// Détecter l'environnement et configurer l'URL de base
const API_BASE_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:8000/api/v1'  // Développement local
    : '/api/v1';  // Production avec proxy nginx

// Client axios configuré
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000, // 30 secondes
    headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
});

// Intercepteur pour gérer les erreurs globalement
apiClient.interceptors.response.use(
    response => response,
    error => {
        // Log l'erreur pour debugging
        console.error('API Error:', error.response || error);
        
        // Gérer les différents types d'erreurs
        if (error.response) {
            // Erreur 401: Problème d'authentification
            if (error.response.status === 401) {
                // Rediriger vers la page de login ou rafraîchir le token
            }
            
            // Erreur 422: Validation de données
            if (error.response.status === 422 && !window.location.pathname.includes('/debug.html')) {
                // Encoder les détails de l'erreur pour les passer dans l'URL
                const errorDetails = encodeURIComponent(JSON.stringify(error.response.data));
                window.location.href = `/422.html?details=${errorDetails}`;
                return new Promise(() => {}); // Bloquer la chaîne de promesses
            }
            
            // Erreur 500: Erreur serveur
            if (error.response.status >= 500 && !window.location.pathname.includes('/debug.html')) {
                window.location.href = '/50x.html';
                return new Promise(() => {}); // Bloquer la chaîne de promesses
            }
        }
        
        return Promise.reject(error);
    }
);

// API Gateway object
const ApiGateway = {
    // Statut du système
    getSystemStatus() {
        return apiClient.get('/status');
    },
    
    getQueueStatus() {
        return apiClient.get('/queue/status');
    },
    
    getComputeNodes() {
        return apiClient.get('/compute-nodes');
    },
    
    // Gestion des tâches
    getNextTask(nodeId) {
        return apiClient.get(`/tasks/next`, {
            params: { node_id: nodeId }
        });
    },
    
    submitTaskResults(taskId, resultData) {
        // Validation des données avant envoi
        if (!taskId || typeof taskId !== 'string') {
            return Promise.reject(new Error('Task ID invalide'));
        }
        
        if (!resultData || typeof resultData !== 'object') {
            return Promise.reject(new Error('Données de résultat invalides'));
        }
        
        // Format attendu par l'API
        const formattedData = {
            task_id: taskId,
            results: resultData.results,
            execution_time: resultData.executionTime || 0,
            memory_usage: resultData.memoryUsage || 0,
            status: resultData.status || 'completed'
        };
        
        return apiClient.post('/tasks/results', formattedData);
    },
    
    // Gestion des simulations
    createSimulation(simulationData) {
        return apiClient.post('/simulations', simulationData);
    },
    
    listSimulations(params = {}) {
        return apiClient.get('/simulations', { params });
    },
    
    getSimulationStatus(simulationId) {
        return apiClient.get(`/simulations/${simulationId}/status`);
    },
    
    getSimulationResults(simulationId) {
        return apiClient.get(`/simulations/${simulationId}/results`);
    },
    
    cancelSimulation(simulationId) {
        return apiClient.delete(`/simulations/${simulationId}`);
    },
    
    // Helpers pour traiter les données
    formatSimulationForSubmission(formData) {
        return {
            simulation_type: formData.type,
            name: formData.name || null,
            description: formData.description || null,
            game_config: formData.gameConfig,
            solver_config: formData.solverConfig
        };
    },
    
    exportStrategyAsJson(strategyData) {
        const dataStr = JSON.stringify(strategyData, null, 2);
        const dataBlob = new Blob([dataStr], {type: 'application/json'});
        
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = `strategy_${new Date().toISOString()}.json`;
        link.click();
        
        // Libérer les ressources
        setTimeout(() => URL.revokeObjectURL(link.href), 100);
    },
    
    // Validation des données
    validateTaskResultFormat(data) {
        const errors = [];
        
        // Vérifier les champs obligatoires
        if (!data.task_id) {
            errors.push("Le champ 'task_id' est requis");
        }
        
        if (!data.results) {
            errors.push("Le champ 'results' est requis");
        }
        
        if (!data.status) {
            errors.push("Le champ 'status' est requis");
        } else if (!['completed', 'failed', 'error'].includes(data.status)) {
            errors.push("Le statut doit être 'completed', 'failed' ou 'error'");
        }
        
        // Vérifier les types de données
        if (data.execution_time && typeof data.execution_time !== 'number') {
            errors.push("'execution_time' doit être un nombre");
        }
        
        if (data.memory_usage && typeof data.memory_usage !== 'number') {
            errors.push("'memory_usage' doit être un nombre");
        }
        
        return {
            isValid: errors.length === 0,
            errors: errors
        };
    }
};
