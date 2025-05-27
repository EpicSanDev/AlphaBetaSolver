// Composant pour visualiser les stratégies GTO
// Ce composant permet d'afficher les stratégies sous forme de matrice de mains ou de graphiques

// Constantes pour la visualisation
const CARD_RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];
const CARD_SUITS = ['s', 'o']; // s = suited, o = offsuit

const StrategyVisualizer = {
    props: {
        strategy: {
            type: Object,
            required: true
        },
        player: {
            type: Number,
            default: 0
        },
        action: {
            type: String,
            default: null // Si null, affiche la stratégie complète
        }
    },
    
    data() {
        return {
            selectedAction: this.action || 'all',
            selectedPlayer: this.player,
            displayMode: 'matrix', // 'matrix' ou 'chart'
            chartInstance: null,
            colorScale: [
                '#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', 
                '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b'
            ]
        };
    },
    
    computed: {
        // Prépare les données pour la visualisation en matrice
        matrixData() {
            if (!this.strategy || !this.strategy.preflop_strategy) {
                return [];
            }
            
            // Création de la matrice 13x13 (cartes de A à 2)
            const matrix = [];
            
            for (let i = 0; i < CARD_RANKS.length; i++) {
                const row = [];
                for (let j = 0; j < CARD_RANKS.length; j++) {
                    // Déterminer si suited ou offsuit
                    const suit = i < j ? 's' : (i > j ? 'o' : 's');
                    // Créer la représentation de la main (ex: "AKs" ou "AKo")
                    const hand = CARD_RANKS[i] + CARD_RANKS[j] + (i === j ? '' : suit);
                    
                    // Trouver la stratégie pour cette main
                    const handStrategy = this.findHandStrategy(hand);
                    
                    row.push({
                        hand,
                        value: handStrategy ? handStrategy.frequency : 0,
                        actions: handStrategy ? handStrategy.actions : {},
                        isEqual: i === j // Paire (ex: AA, KK, etc.)
                    });
                }
                matrix.push(row);
            }
            
            return matrix;
        },
        
        // Données pour le graphique
        chartData() {
            if (!this.strategy || !this.strategy.preflop_strategy) {
                return null;
            }
            
            // Extraire les actions uniques
            const actions = new Set();
            Object.values(this.strategy.preflop_strategy).forEach(hand => {
                Object.keys(hand.actions).forEach(action => actions.add(action));
            });
            
            // Créer les datasets
            const datasets = Array.from(actions).map((action, index) => {
                const data = [];
                const borderColor = this.getActionColor(action);
                const backgroundColor = this.getActionColor(action, 0.5);
                
                // Extraire les données pour chaque action
                Object.entries(this.strategy.preflop_strategy).forEach(([hand, strategy]) => {
                    if (strategy.actions[action]) {
                        data.push({
                            x: hand,
                            y: strategy.actions[action]
                        });
                    }
                });
                
                return {
                    label: action,
                    data,
                    borderColor,
                    backgroundColor,
                    borderWidth: 1
                };
            });
            
            return {
                datasets
            };
        }
    },
    
    methods: {
        // Trouve la stratégie pour une main spécifique
        findHandStrategy(hand) {
            if (!this.strategy || !this.strategy.preflop_strategy) {
                return null;
            }
            
            // Récupérer la stratégie pour cette main
            const handStrategy = this.strategy.preflop_strategy[hand];
            
            if (!handStrategy) {
                return null;
            }
            
            // Si une action spécifique est sélectionnée, filtrer les données
            if (this.selectedAction !== 'all') {
                const actionFrequency = handStrategy.actions[this.selectedAction] || 0;
                return {
                    frequency: actionFrequency,
                    actions: { [this.selectedAction]: actionFrequency }
                };
            }
            
            return handStrategy;
        },
        
        // Renvoie une couleur pour chaque action
        getActionColor(action, alpha = 1) {
            const actionColors = {
                'fold': `rgba(231, 76, 60, ${alpha})`,
                'check': `rgba(241, 196, 15, ${alpha})`,
                'call': `rgba(46, 204, 113, ${alpha})`,
                'bet': `rgba(52, 152, 219, ${alpha})`,
                'raise': `rgba(155, 89, 182, ${alpha})`,
                'all-in': `rgba(0, 0, 0, ${alpha})`
            };
            
            return actionColors[action.toLowerCase()] || `rgba(0, 0, 0, ${alpha})`;
        },
        
        // Génère une couleur en fonction d'une valeur entre 0 et 1
        getHeatMapColor(value) {
            if (value === null || value === undefined) {
                return '#f5f5f5'; // Gris clair pour les valeurs manquantes
            }
            
            // Limiter la valeur entre 0 et 1
            const clampedValue = Math.max(0, Math.min(1, value));
            // Calculer l'index dans l'échelle de couleurs
            const index = Math.floor(clampedValue * (this.colorScale.length - 1));
            return this.colorScale[index];
        },
        
        // Initialise le graphique Chart.js
        initChart() {
            if (this.chartInstance) {
                this.chartInstance.destroy();
            }
            
            const ctx = document.getElementById('strategyChart');
            if (!ctx || !this.chartData) return;
            
            this.chartInstance = new Chart(ctx, {
                type: 'scatter',
                data: this.chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Main'
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Fréquence (%)'
                            },
                            min: 0,
                            max: 100
                        }
                    },
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`;
                                }
                            }
                        },
                        legend: {
                            display: true,
                            position: 'top'
                        }
                    }
                }
            });
        },
        
        // Change le mode d'affichage
        changeDisplayMode(mode) {
            this.displayMode = mode;
            if (mode === 'chart') {
                // Initialiser le graphique au prochain cycle de rendu
                this.$nextTick(() => {
                    this.initChart();
                });
            }
        },
        
        // Change l'action sélectionnée
        changeAction(action) {
            this.selectedAction = action;
            if (this.displayMode === 'chart') {
                this.$nextTick(() => {
                    this.initChart();
                });
            }
        }
    },
    
    // Surveiller les changements de props
    watch: {
        strategy() {
            if (this.displayMode === 'chart') {
                this.$nextTick(() => {
                    this.initChart();
                });
            }
        }
    },
    
    // Nettoyer le graphique à la destruction du composant
    beforeUnmount() {
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }
    },
    
    // Template pour le composant
    template: `
        <div class="strategy-visualizer">
            <div class="controls">
                <div class="form-group">
                    <label>Mode d'affichage:</label>
                    <div class="btn-group">
                        <button class="btn" :class="{'btn-primary': displayMode === 'matrix'}" @click="changeDisplayMode('matrix')">
                            Matrice
                        </button>
                        <button class="btn" :class="{'btn-primary': displayMode === 'chart'}" @click="changeDisplayMode('chart')">
                            Graphique
                        </button>
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Action:</label>
                    <select v-model="selectedAction" class="form-control" @change="changeAction(selectedAction)">
                        <option value="all">Toutes les actions</option>
                        <option value="fold">Fold</option>
                        <option value="check">Check</option>
                        <option value="call">Call</option>
                        <option value="bet">Bet</option>
                        <option value="raise">Raise</option>
                        <option value="all-in">All-in</option>
                    </select>
                </div>
            </div>
            
            <!-- Affichage en matrice -->
            <div v-if="displayMode === 'matrix'" class="matrix-view">
                <table class="hand-matrix">
                    <thead>
                        <tr>
                            <th></th>
                            <th v-for="rank in CARD_RANKS" :key="rank">{{ rank }}</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="(row, rowIndex) in matrixData" :key="rowIndex">
                            <th>{{ CARD_RANKS[rowIndex] }}</th>
                            <td v-for="(cell, colIndex) in row" :key="colIndex" 
                                :style="{ backgroundColor: getHeatMapColor(cell.value) }"
                                :class="{ 'pair': cell.isEqual }">
                                <div class="hand-label">{{ cell.hand }}</div>
                                <div class="frequency">{{ (cell.value * 100).toFixed(1) }}%</div>
                                <div v-if="selectedAction === 'all'" class="actions">
                                    <div v-for="(freq, action) in cell.actions" :key="action" class="action">
                                        <span class="action-name">{{ action }}:</span>
                                        <span class="action-freq">{{ (freq * 100).toFixed(1) }}%</span>
                                    </div>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <!-- Affichage en graphique -->
            <div v-else-if="displayMode === 'chart'" class="chart-view">
                <canvas id="strategyChart" height="400"></canvas>
            </div>
        </div>
    `
};
