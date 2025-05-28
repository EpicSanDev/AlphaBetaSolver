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
        
        // Gérer les erreurs d'authentification si nécessaire
        if (error.response && error.response.status === 401) {
            // Rediriger vers la page de login ou rafraîchir le token
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
    }
};
