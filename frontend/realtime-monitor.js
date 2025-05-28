// Real-time monitoring using WebSocket
class RealtimeMonitor {
    constructor() {
        this.ws = null;
        this.reconnectInterval = 5000; // 5 secondes
        this.maxReconnectAttempts = 10;
        this.reconnectAttempts = 0;
        this.listeners = new Map();
        this.isConnected = false;
        
        this.connect();
    }
    
    connect() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connecté');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                
                // S'abonner aux mises à jour système
                this.subscribeToSystem();
                
                // Notifier les listeners
                this.notifyListeners('connected', { connected: true });
            };
            
            this.ws.onmessage = (event) => {
                try {
                    // Handle non-JSON text messages
                    if (typeof event.data === 'string') {
                        // Check for common server text responses
                        if (event.data.startsWith('Connection') || 
                            event.data.startsWith('Echo:')) {
                            console.log('Received text message:', event.data);
                            return;
                        }
                        
                        // Try to parse as JSON
                        try {
                            const message = JSON.parse(event.data);
                            this.handleMessage(message);
                        } catch (jsonError) {
                            // Not valid JSON but not a recognized text message
                            console.log('Received non-JSON message:', event.data);
                        }
                    } else {
                        // Binary data or other types
                        console.log('Received non-string message type:', typeof event.data);
                    }
                } catch (error) {
                    console.error('Error in WebSocket message handler:', error);
                }
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket fermé');
                this.isConnected = false;
                this.notifyListeners('connected', { connected: false });
                this.attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('Erreur WebSocket:', error);
                this.isConnected = false;
            };
            
        } catch (error) {
            console.error('Erreur connexion WebSocket:', error);
            this.attemptReconnect();
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Tentative de reconnexion ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectInterval);
        } else {
            console.error('Nombre maximum de tentatives de reconnexion atteint');
        }
    }
    
    handleMessage(message) {
        const { type, data, simulation_id } = message;
        
        switch (type) {
            case 'simulation_update':
                this.notifyListeners('simulation_update', { simulation_id, ...data });
                break;
                
            case 'system_update':
                this.notifyListeners('system_update', data);
                break;
                
            case 'compute_node_update':
                this.notifyListeners('compute_node_update', data);
                break;
                
            case 'subscription_confirmed':
                console.log(`Abonné à la simulation: ${simulation_id}`);
                break;
                
            case 'system_subscription_confirmed':
                console.log('Abonné aux mises à jour système');
                break;
                
            case 'pong':
                // Réponse au ping
                break;
                
            default:
                console.log('Message WebSocket non géré:', message);
        }
    }
    
    subscribeToSimulation(simulationId) {
        if (this.isConnected) {
            this.send({
                type: 'subscribe_simulation',
                simulation_id: simulationId
            });
        }
    }
    
    subscribeToSystem() {
        if (this.isConnected) {
            this.send({
                type: 'subscribe_system'
            });
        }
    }
    
    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
    }
    
    // Système d'événements
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }
    
    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }
    
    notifyListeners(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error('Erreur dans listener:', error);
                }
            });
        }
    }
    
    ping() {
        this.send({ type: 'ping' });
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

// Fonctions utilitaires pour le monitoring
const MonitoringUtils = {
    formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    formatDuration(seconds) {
        if (!seconds) return '0s';
        
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes}min`;
        } else if (minutes > 0) {
            return `${minutes}min ${secs}s`;
        } else {
            return `${secs}s`;
        }
    },
    
    formatPercentage(value, decimals = 1) {
        return `${(value || 0).toFixed(decimals)}%`;
    },
    
    getStatusColor(status) {
        const colors = {
            'available': '#28a745',
            'busy': '#ffc107',
            'offline': '#dc3545',
            'running': '#007bff',
            'completed': '#28a745',
            'failed': '#dc3545',
            'pending': '#6c757d',
            'cancelled': '#fd7e14'
        };
        return colors[status] || '#6c757d';
    },
    
    createProgressBar(percentage, className = '') {
        return `
            <div class="progress-bar ${className}">
                <div class="progress-fill" style="width: ${percentage}%"></div>
            </div>
        `;
    },
    
    createStatusBadge(status) {
        const color = this.getStatusColor(status);
        return `<span class="status-badge" style="background-color: ${color}">${status}</span>`;
    }
};

// Composant de monitoring temps réel
const RealtimeComponents = {
    createSystemMetricsWidget(data) {
        return `
            <div class="metrics-widget">
                <h4>🖥️ Métriques Système</h4>
                <div class="metrics-grid">
                    <div class="metric-item">
                        <span class="metric-label">CPU</span>
                        <span class="metric-value">${MonitoringUtils.formatPercentage(data.cpu_usage)}</span>
                        ${MonitoringUtils.createProgressBar(data.cpu_usage || 0, 'cpu')}
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Mémoire</span>
                        <span class="metric-value">${MonitoringUtils.formatPercentage(data.memory_usage)}</span>
                        ${MonitoringUtils.createProgressBar(data.memory_usage || 0, 'memory')}
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Simulations actives</span>
                        <span class="metric-value">${data.active_simulations || 0}</span>
                    </div>
                </div>
            </div>
        `;
    },
    
    createComputeNodesWidget(nodes) {
        const totalNodes = nodes.length;
        const activeNodes = nodes.filter(n => n.status !== 'offline').length;
        const totalCapacity = nodes.reduce((sum, n) => sum + n.max_concurrent_tasks, 0);
        const currentUsage = nodes.reduce((sum, n) => sum + n.current_tasks, 0);
        
        return `
            <div class="compute-nodes-widget">
                <h4>⚡ Cluster de Calcul</h4>
                <div class="cluster-summary">
                    <div class="summary-item">
                        <span class="summary-label">Nœuds actifs</span>
                        <span class="summary-value">${activeNodes}/${totalNodes}</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-label">Utilisation</span>
                        <span class="summary-value">${currentUsage}/${totalCapacity}</span>
                        ${MonitoringUtils.createProgressBar((currentUsage / totalCapacity) * 100, 'utilization')}
                    </div>
                </div>
                <div class="nodes-list">
                    ${nodes.map(node => this.createNodeItem(node)).join('')}
                </div>
            </div>
        `;
    },
    
    createNodeItem(node) {
        const utilizationPercentage = (node.current_tasks / node.max_concurrent_tasks) * 100;
        
        return `
            <div class="node-item" data-node-id="${node.node_id}">
                <div class="node-header">
                    <span class="node-name">${node.node_id}</span>
                    ${MonitoringUtils.createStatusBadge(node.status)}
                </div>
                <div class="node-details">
                    <div class="node-spec">
                        <span>${node.platform} ${node.architecture}</span>
                        <span>${node.cpu_count} CPUs</span>
                        <span>${MonitoringUtils.formatBytes(node.memory_total)}</span>
                    </div>
                    <div class="node-usage">
                        <span>Tâches: ${node.current_tasks}/${node.max_concurrent_tasks}</span>
                        ${MonitoringUtils.createProgressBar(utilizationPercentage, 'node-utilization')}
                    </div>
                    <div class="node-stats">
                        <span>CPU: ${MonitoringUtils.formatPercentage(node.cpu_usage)}</span>
                        <span>RAM: ${MonitoringUtils.formatPercentage(node.memory_usage)}</span>
                        <span>Complétées: ${node.total_tasks_completed || 0}</span>
                    </div>
                </div>
            </div>
        `;
    },
    
    createSimulationProgress(simulation) {
        return `
            <div class="simulation-progress" data-simulation-id="${simulation.simulation_id}">
                <div class="simulation-header">
                    <h5>${simulation.name || simulation.simulation_id}</h5>
                    ${MonitoringUtils.createStatusBadge(simulation.status)}
                </div>
                <div class="progress-details">
                    ${MonitoringUtils.createProgressBar(simulation.progress_percentage || 0, 'simulation-progress')}
                    <div class="progress-stats">
                        <span>Progrès: ${MonitoringUtils.formatPercentage(simulation.progress_percentage)}</span>
                        <span>Itérations: ${simulation.iterations_completed || 0}</span>
                        ${simulation.estimated_time_remaining ? 
                          `<span>Temps restant: ${MonitoringUtils.formatDuration(simulation.estimated_time_remaining)}</span>` : 
                          ''}
                    </div>
                </div>
            </div>
        `;
    }
};

// Export pour utilisation dans l'application principale
window.RealtimeMonitor = RealtimeMonitor;
window.MonitoringUtils = MonitoringUtils;
window.RealtimeComponents = RealtimeComponents;
