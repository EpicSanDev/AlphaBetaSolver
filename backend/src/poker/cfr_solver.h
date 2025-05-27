#pragma once

#include "game_tree.h"
#include <memory>
#include <unordered_map>
#include <random>

namespace poker {

// Configuration pour le solveur CFR
struct CFRConfig {
    int max_iterations = 1000;
    double target_exploitability = 0.005; // 0.5% du pot
    bool use_chance_sampling = true;
    bool use_discounting = true;
    double alpha = 1.5; // Pour le discounting
    double beta = 0.0;
    int checkpoint_frequency = 100; // Sauvegarder tous les N iterations
    
    std::string to_string() const;
};

// Résultats du solveur
struct CFRResult {
    int iterations_completed;
    double final_exploitability;
    double convergence_time_seconds;
    bool converged;
    std::string status_message;
    
    std::string to_string() const;
};

// Interface pour le solveur CFR
class CFRSolver {
public:
    CFRSolver(std::shared_ptr<GameAbstraction> abstraction, const CFRConfig& config = CFRConfig{});
    virtual ~CFRSolver() = default;
    
    // Résoudre le jeu
    virtual CFRResult solve(const GameState& initial_state) = 0;
    
    // Obtenir la stratégie optimale pour un nœud
    virtual std::vector<double> get_strategy(const GameState& state, int player) const = 0;
    
    // Calculer l'exploitabilité actuelle
    virtual double calculate_exploitability(const GameState& root_state) const = 0;
    
    // Sauvegarder/charger l'état du solveur
    virtual void save_checkpoint(const std::string& filename) const = 0;
    virtual void load_checkpoint(const std::string& filename) = 0;
    
protected:
    std::shared_ptr<GameAbstraction> abstraction_;
    CFRConfig config_;
    int current_iteration_;
    std::unordered_map<std::string, std::shared_ptr<GameNode>> node_map_;
    
    // Obtenir ou créer un nœud
    std::shared_ptr<GameNode> get_or_create_node(const GameState& state, int player);
    
    // Génération de clé unique pour un état de jeu
    virtual std::string state_to_key(const GameState& state, int player) const;

protected:
    // Fonction auxiliaire pour le calcul de la meilleure réponse, utilisable par les sous-classes
    double best_response_traversal(const GameState& state, int br_player,
                                   const std::vector<Hand>& all_hands_for_terminal_eval) const;
};

// Implémentation standard de CFR
class VanillaCFR : public CFRSolver {
public:
    VanillaCFR(std::shared_ptr<GameAbstraction> abstraction, const CFRConfig& config = CFRConfig{});
    
    CFRResult solve(const GameState& initial_state) override;
    std::vector<double> get_strategy(const GameState& state, int player) const override;
    double calculate_exploitability(const GameState& root_state) const override;
    
    void save_checkpoint(const std::string& filename) const override;
    void load_checkpoint(const std::string& filename) override;
    
private:
    // Algorithme CFR récursif
    std::vector<double> cfr(const GameState& state, std::vector<Hand>& hands, 
                           std::vector<double>& reach_probabilities, int iteration);
    
    // Calcul de la valeur d'un nœud terminal
    std::vector<double> get_terminal_values(const GameState& state, const std::vector<Hand>& hands) const;
    
    // Mise à jour des regrets avec discounting
    void update_regrets_with_discounting(std::shared_ptr<GameNode> node, 
                                       const std::vector<double>& regrets, int iteration);
    
    // Calcul de la valeur d'une stratégie (helper pour calculate_exploitability)
    double calculate_strategy_value(const GameState& state, int player) const;

};

// CFR avec échantillonnage de chance (MCCFR)
class ChanceSamplingCFR : public CFRSolver {
public:
    ChanceSamplingCFR(std::shared_ptr<GameAbstraction> abstraction, const CFRConfig& config = CFRConfig{});
    
    CFRResult solve(const GameState& initial_state) override;
    std::vector<double> get_strategy(const GameState& state, int player) const override;
    double calculate_exploitability(const GameState& root_state) const override;
    
    void save_checkpoint(const std::string& filename) const override;
    void load_checkpoint(const std::string& filename) override;
    
private:
    std::mt19937 rng_;
    
    // MCCFR avec échantillonnage
    std::vector<double> mccfr(const GameState& state, const Hand& sampled_hand, 
                             std::vector<double>& reach_probabilities, int iteration, int player);
    
    // Échantillonner une main aléatoire compatible avec l'état
    Hand sample_hand(const GameState& state);
    
    // Échantillonner une action selon la stratégie
    int sample_action(const std::vector<double>& strategy);
    
    // Calcul de la valeur d'une stratégie (helper pour calculate_exploitability)
    double calculate_strategy_value(const GameState& state, int player) const;
};

// CFR+ (version améliorée avec regret matching +)
class CFRPlus : public CFRSolver {
public:
    CFRPlus(std::shared_ptr<GameAbstraction> abstraction, const CFRConfig& config = CFRConfig{});
    
    CFRResult solve(const GameState& initial_state) override;
    std::vector<double> get_strategy(const GameState& state, int player) const override;
    double calculate_exploitability(const GameState& root_state) const override;
    
    void save_checkpoint(const std::string& filename) const override;
    void load_checkpoint(const std::string& filename) override;
    
private:
    // CFR+ utilise des regrets cumulés légèrement différents
    std::vector<double> cfr_plus(const GameState& state, std::vector<Hand>& hands,
                                std::vector<double>& reach_probabilities, int iteration);
    
    // Regret matching + (ne garde que les regrets positifs)
    std::vector<double> regret_matching_plus(const std::vector<double>& regrets) const;
    
    // Calcul de la valeur d'une stratégie (helper pour calculate_exploitability)
    double calculate_strategy_value(const GameState& state, int player) const;
};

// Factory pour créer le bon type de solveur
class CFRSolverFactory {
public:
    enum class SolverType {
        VANILLA_CFR,
        CHANCE_SAMPLING_CFR, 
        CFR_PLUS
    };
    
    static std::unique_ptr<CFRSolver> create_solver(
        SolverType type,
        std::shared_ptr<GameAbstraction> abstraction,
        const CFRConfig& config = CFRConfig{}
    );
};

} // namespace poker
