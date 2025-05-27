#include "cfr_solver.h"
#include "evaluator.h"
#include <sstream>
#include <chrono>
#include <algorithm>
#include <fstream>
#include <iostream>
#include <limits> // Pour std::numeric_limits

namespace poker {

std::string CFRConfig::to_string() const {
    std::ostringstream oss;
    oss << "CFRConfig{max_iterations=" << max_iterations
        << ", target_exploitability=" << target_exploitability
        << ", use_chance_sampling=" << use_chance_sampling
        << ", use_discounting=" << use_discounting
        << "}";
    return oss.str();
}

std::string CFRResult::to_string() const {
    std::ostringstream oss;
    oss << "CFRResult{iterations=" << iterations_completed
        << ", exploitability=" << final_exploitability
        << ", time=" << convergence_time_seconds << "s"
        << ", converged=" << converged
        << "}";
    return oss.str();
}

// CFRSolver base implementation
CFRSolver::CFRSolver(std::shared_ptr<GameAbstraction> abstraction, const CFRConfig& config)
    : abstraction_(abstraction), config_(config), current_iteration_(0) {}

std::shared_ptr<GameNode> CFRSolver::get_or_create_node(const GameState& state, int player) {
    std::string key = state_to_key(state, player);
    
    auto it = node_map_.find(key);
    if (it != node_map_.end()) {
        return it->second;
    }
    
    auto node = std::make_shared<GameNode>(state, player);
    node_map_[key] = node;
    return node;
}

std::string CFRSolver::state_to_key(const GameState& state, int player) const {
    std::ostringstream oss;
    oss << "p" << player << "_s" << state.street << "_pot" << state.pot 
        << "_cp" << state.current_player << "_board" << board_to_string(state.board);
    
    // Ajouter les mises actuelles
    for (size_t i = 0; i < state.bets.size(); ++i) {
        oss << "_bet" << i << "_" << state.bets[i];
    }
    
    return oss.str();
}

// VanillaCFR implementation
VanillaCFR::VanillaCFR(std::shared_ptr<GameAbstraction> abstraction, const CFRConfig& config)
    : CFRSolver(abstraction, config) {}

CFRResult VanillaCFR::solve(const GameState& initial_state) {
    auto start_time = std::chrono::high_resolution_clock::now();
    
    CFRResult result;
    result.converged = false;
    
    // Générer toutes les mains possibles pour le jeu
    std::vector<Hand> all_hands;
    auto cards = all_cards();
    for (size_t i = 0; i < cards.size(); ++i) {
        for (size_t j = i + 1; j < cards.size(); ++j) {
            all_hands.emplace_back(cards[i], cards[j]);
        }
    }
    
    for (int iteration = 1; iteration <= config_.max_iterations; ++iteration) {
        current_iteration_ = iteration;
        
        // Initialiser les probabilités d'atteinte
        std::vector<double> reach_probs(initial_state.num_players, 1.0);
        
        // Exécuter une itération de CFR
        std::vector<Hand> hands = all_hands; // Copie pour cette itération
        cfr(initial_state, hands, reach_probs, iteration);
        
        // Vérifier la convergence périodiquement
        if (iteration % 50 == 0) {
            double exploitability = calculate_exploitability(initial_state);
            std::cout << "Iteration " << iteration << ": Exploitability = " 
                      << exploitability << std::endl;
            
            if (exploitability <= config_.target_exploitability) {
                result.converged = true;
                break;
            }
        }
        
        // Checkpoint périodique
        if (config_.checkpoint_frequency > 0 && iteration % config_.checkpoint_frequency == 0) {
            save_checkpoint("checkpoint_" + std::to_string(iteration) + ".bin");
        }
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    
    result.iterations_completed = current_iteration_;
    result.final_exploitability = calculate_exploitability(initial_state);
    result.convergence_time_seconds = duration.count() / 1000.0;
    result.status_message = result.converged ? "Converged" : "Max iterations reached";
    
    return result;
}

std::vector<double> VanillaCFR::cfr(const GameState& state, std::vector<Hand>& hands,
                                   std::vector<double>& reach_probabilities, int iteration) {
    
    if (state.is_terminal()) {
        return get_terminal_values(state, hands);
    }
    
    int player = state.current_player;
    auto node = get_or_create_node(state, player);
    
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    if (actions.empty()) {
        return std::vector<double>(state.num_players, 0.0);
    }
    
    std::vector<double> strategy = node->get_strategy();
    std::vector<double> action_values(actions.size());
    std::vector<double> node_values(state.num_players, 0.0);
    
    // Calculer la valeur de chaque action
    for (size_t i = 0; i < actions.size(); ++i) {
        GameState next_state = state.apply_action(actions[i]);
        
        // Mettre à jour les probabilités d'atteinte
        std::vector<double> next_reach_probs = reach_probabilities;
        next_reach_probs[player] *= strategy[i];
        
        std::vector<double> action_result = cfr(next_state, hands, next_reach_probs, iteration);
        action_values[i] = action_result[player];
        
        // Accumuler les valeurs pondérées par la stratégie
        for (int p = 0; p < state.num_players; ++p) {
            node_values[p] += strategy[i] * action_result[p];
        }
    }
    
    // Calculer les regrets
    std::vector<double> regrets(actions.size());
    for (size_t i = 0; i < actions.size(); ++i) {
        regrets[i] = action_values[i] - node_values[player];
    }
    
    // Mettre à jour les regrets avec ou sans discounting
    if (config_.use_discounting) {
        update_regrets_with_discounting(node, regrets, iteration);
    } else {
        node->update_regret(regrets);
    }
    
    // Mettre à jour la somme des stratégies
    double reach_prob = reach_probabilities[player];
    std::vector<double> weighted_strategy(strategy.size());
    for (size_t i = 0; i < strategy.size(); ++i) {
        weighted_strategy[i] = reach_prob * strategy[i];
    }
    node->update_strategy_sum(weighted_strategy);
    
    return node_values;
}

std::vector<double> VanillaCFR::get_terminal_values(const GameState& state, const std::vector<Hand>& hands) const {
    // Simplification: retourner les payoffs du state
    return state.get_payoffs();
}

void VanillaCFR::update_regrets_with_discounting(std::shared_ptr<GameNode> node,
                                                 const std::vector<double>& regrets, int iteration) {
    double discount_factor = std::pow(iteration, -config_.alpha);
    std::vector<double> discounted_regrets(regrets.size());
    
    for (size_t i = 0; i < regrets.size(); ++i) {
        discounted_regrets[i] = regrets[i] * discount_factor;
    }
    
    node->update_regret(discounted_regrets);
}

std::vector<double> VanillaCFR::get_strategy(const GameState& state, int player) const {
    auto node = node_map_.find(state_to_key(state, player));
    if (node != node_map_.end()) {
        return node->second->get_average_strategy();
    }
    
    // Stratégie uniforme par défaut
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    if (actions.empty()) return {};
    
    return std::vector<double>(actions.size(), 1.0 / actions.size());
}

// Fonction auxiliaire récursive pour calculer la valeur de la meilleure réponse (maintenant dans CFRSolver)
double CFRSolver::best_response_traversal(const GameState& state, int br_player, 
                                           const std::vector<Hand>& all_hands_for_terminal_eval) const {
    if (state.is_terminal()) {
        return state.get_payoffs()[br_player];
    }

    int current_player = state.current_player;
    std::vector<Action> actions = this->abstraction_->get_abstracted_actions(state);
    if (actions.empty()) {
        return state.get_payoffs()[br_player];
    }

    if (current_player == br_player) {
        double max_value = -std::numeric_limits<double>::infinity();
        for (const Action& action : actions) {
            GameState next_state = state.apply_action(action);
            max_value = std::max(max_value, this->best_response_traversal(next_state, br_player, all_hands_for_terminal_eval));
        }
        return max_value;
    } else {
        auto node_iter = this->node_map_.find(this->state_to_key(state, current_player));
        std::vector<double> opponent_strategy;

        if (node_iter != this->node_map_.end() && !node_iter->second->actions.empty()) {
            opponent_strategy = node_iter->second->get_average_strategy();
            if (opponent_strategy.size() != actions.size()) {
                opponent_strategy.assign(actions.size(), 1.0 / actions.size());
            }
        } else {
            if (actions.empty()) return state.get_payoffs()[br_player];
            opponent_strategy.assign(actions.size(), 1.0 / actions.size());
        }
        
        double expected_value = 0.0;
        for (size_t i = 0; i < actions.size(); ++i) {
            GameState next_state = state.apply_action(actions[i]);
            expected_value += opponent_strategy[i] * this->best_response_traversal(next_state, br_player, all_hands_for_terminal_eval);
        }
        return expected_value;
    }
}


double VanillaCFR::calculate_exploitability(const GameState& root_state) const {
    if (root_state.num_players != 2) {
        std::cerr << "Avertissement: Calcul d'exploitabilité pour N>2 joueurs non standard." << std::endl;
        return 0.01; // Placeholder pour N joueurs
    }

    // Générer toutes les combinaisons de mains possibles pour les deux joueurs
    auto all_cards_vec = all_cards(); // Fonction définie dans card.h
    std::vector<std::pair<Hand, Hand>> all_hand_pairs;
    
    // Générer toutes les paires de mains possibles (sans overlap)
    for (size_t i = 0; i < all_cards_vec.size(); ++i) {
        for (size_t j = i + 1; j < all_cards_vec.size(); ++j) {
            Hand hand1(all_cards_vec[i], all_cards_vec[j]);
            
            for (size_t k = 0; k < all_cards_vec.size(); ++k) {
                if (k == i || k == j) continue;
                
                for (size_t l = k + 1; l < all_cards_vec.size(); ++l) {
                    if (l == i || l == j) continue;
                    
                    Hand hand2(all_cards_vec[k], all_cards_vec[l]);
                    all_hand_pairs.emplace_back(hand1, hand2);
                }
            }
        }
    }
    
    if (all_hand_pairs.empty()) {
        return 0.01; // Éviter division par zéro
    }

    double total_exploitability = 0.0;
    
    // Calculer l'exploitabilité moyenne sur toutes les combinaisons de mains
    for (const auto& hand_pair : all_hand_pairs) {
        // Créer un état de jeu avec ces mains spécifiques
        GameState current_state = root_state;
        current_state.player_hands = {hand_pair.first, hand_pair.second};
        
        // Calculer la valeur avec les stratégies actuelles
        double current_value_p0 = calculate_strategy_value(current_state, 0);
        double current_value_p1 = calculate_strategy_value(current_state, 1);
        
        // Calculer les valeurs de meilleure réponse
        double br_value_p0 = best_response_traversal(current_state, 0, {});
        double br_value_p1 = best_response_traversal(current_state, 1, {});
        
        // L'exploitabilité est la différence entre BR et stratégie actuelle
        double exploit_p0 = br_value_p0 - current_value_p0;
        double exploit_p1 = br_value_p1 - current_value_p1;
        
        // Pour un jeu à somme nulle, on peut normaliser
        total_exploitability += (exploit_p0 + exploit_p1) / 2.0;
    }
    
    return total_exploitability / all_hand_pairs.size();
}

// Fonction auxiliaire pour calculer la valeur avec la stratégie actuelle
double VanillaCFR::calculate_strategy_value(const GameState& state, int player) const {
    if (state.is_terminal()) {
        return state.get_payoffs()[player];
    }
    
    int current_player = state.current_player;
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    
    if (actions.empty()) {
        return state.get_payoffs()[player];
    }
    
    // Obtenir la stratégie du joueur actuel
    std::vector<double> strategy = get_strategy(state, current_player);
    
    double expected_value = 0.0;
    for (size_t i = 0; i < actions.size(); ++i) {
        GameState next_state = state.apply_action(actions[i]);
        double action_value = calculate_strategy_value(next_state, player);
        expected_value += strategy[i] * action_value;
    }
    
    return expected_value;
}

void VanillaCFR::save_checkpoint(const std::string& filename) const {
    std::ofstream file(filename, std::ios::binary);
    if (!file) {
        std::cerr << "Erreur: Impossible de sauvegarder le checkpoint " << filename << std::endl;
        return;
    }
    
    // Sauvegarder l'itération actuelle
    file.write(reinterpret_cast<const char*>(&current_iteration_), sizeof(current_iteration_));
    
    // Sauvegarder le nombre de nœuds
    size_t num_nodes = node_map_.size();
    file.write(reinterpret_cast<const char*>(&num_nodes), sizeof(num_nodes));
    
    // Sauvegarder chaque nœud
    for (const auto& pair : node_map_) {
        const std::string& key = pair.first;
        const auto& node = pair.second;
        
        // Sauvegarder la clé
        size_t key_size = key.size();
        file.write(reinterpret_cast<const char*>(&key_size), sizeof(key_size));
        file.write(key.c_str(), key_size);
        
        // Sauvegarder les données du nœud
        size_t regret_size = node->regret_sum.size();
        file.write(reinterpret_cast<const char*>(&regret_size), sizeof(regret_size));
        file.write(reinterpret_cast<const char*>(node->regret_sum.data()), 
                   regret_size * sizeof(double));
        
        size_t strategy_size = node->strategy_sum.size();
        file.write(reinterpret_cast<const char*>(&strategy_size), sizeof(strategy_size));
        file.write(reinterpret_cast<const char*>(node->strategy_sum.data()), 
                   strategy_size * sizeof(double));
    }
    
    std::cout << "Checkpoint sauvegardé: " << filename << std::endl;
}

void VanillaCFR::load_checkpoint(const std::string& filename) {
    std::ifstream file(filename, std::ios::binary);
    if (!file) {
        std::cerr << "Erreur: Impossible de charger le checkpoint " << filename << std::endl;
        return;
    }
    
    // Charger l'itération
    file.read(reinterpret_cast<char*>(&current_iteration_), sizeof(current_iteration_));
    
    // Charger le nombre de nœuds
    size_t num_nodes;
    file.read(reinterpret_cast<char*>(&num_nodes), sizeof(num_nodes));
    
    // Effacer les nœuds existants
    node_map_.clear();
    
    // Charger chaque nœud
    for (size_t i = 0; i < num_nodes; ++i) {
        // Charger la clé
        size_t key_size;
        file.read(reinterpret_cast<char*>(&key_size), sizeof(key_size));
        std::string key(key_size, '\0');
        file.read(&key[0], key_size);
        
        // Charger les données de regret
        size_t regret_size;
        file.read(reinterpret_cast<char*>(&regret_size), sizeof(regret_size));
        std::vector<double> regret_sum(regret_size);
        file.read(reinterpret_cast<char*>(regret_sum.data()), 
                  regret_size * sizeof(double));
        
        // Charger les données de stratégie
        size_t strategy_size;
        file.read(reinterpret_cast<char*>(&strategy_size), sizeof(strategy_size));
        std::vector<double> strategy_sum(strategy_size);
        file.read(reinterpret_cast<char*>(strategy_sum.data()), 
                  strategy_size * sizeof(double));
        
        // Reconstruire le GameNode
        // Note: Nous créons un nœud temporaire car nous n'avons que la clé
        // En pratique, le nœud sera recréé lors de la prochaine traversée CFR
        // avec le bon GameState, mais nous restaurons les données apprises
        try {
            // Décoder la clé pour extraire les informations de base
            // Format de clé typique: "player_actions_board_hand"
            // Pour l'instant, créer un nœud placeholder qui sera remplacé
            GameState placeholder_state;
            placeholder_state.num_players = 2; // Valeur par défaut
            
            auto node = std::make_shared<GameNode>(placeholder_state, 0);
            node->regret_sum = std::move(regret_sum);
            node->strategy_sum = std::move(strategy_sum);
            
            // Stocker dans la map pour récupération ultérieure
            node_map_[key] = node;
            
        } catch (const std::exception& e) {
            std::cerr << "Erreur lors de la reconstruction du nœud " << key 
                      << ": " << e.what() << std::endl;
        }
    }
    
    std::cout << "Checkpoint chargé: " << filename << std::endl;
}

// Déclaration de la fonction privée pour la classe VanillaCFR dans le .h serait nécessaire
// double VanillaCFR::best_response_traversal(const GameState& state, int br_player, 
//                                            const std::vector<Hand>& all_hands_for_terminal_eval) const;


// ChanceSamplingCFR implementation
ChanceSamplingCFR::ChanceSamplingCFR(std::shared_ptr<GameAbstraction> abstraction, const CFRConfig& config)
    : CFRSolver(abstraction, config), rng_(std::random_device{}()) {}

CFRResult ChanceSamplingCFR::solve(const GameState& initial_state) {
    auto start_time = std::chrono::high_resolution_clock::now();
    
    CFRResult result;
    result.converged = false;
    
    for (int iteration = 1; iteration <= config_.max_iterations; ++iteration) {
        current_iteration_ = iteration;
        
        // Échantillonner une main pour cette itération
        Hand sampled_hand = sample_hand(initial_state);
        
        for (int player = 0; player < initial_state.num_players; ++player) {
            std::vector<double> reach_probs(initial_state.num_players, 1.0);
            mccfr(initial_state, sampled_hand, reach_probs, iteration, player);
        }
        
        // Vérification de convergence moins fréquente
        if (iteration % 100 == 0) {
            double exploitability = calculate_exploitability(initial_state);
            std::cout << "MCCFR Iteration " << iteration << ": Exploitability = " 
                      << exploitability << std::endl;
            
            if (exploitability <= config_.target_exploitability) {
                result.converged = true;
                break;
            }
        }
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    
    result.iterations_completed = current_iteration_;
    result.final_exploitability = calculate_exploitability(initial_state);
    result.convergence_time_seconds = duration.count() / 1000.0;
    result.status_message = result.converged ? "Converged" : "Max iterations reached";
    
    return result;
}

std::vector<double> ChanceSamplingCFR::mccfr(const GameState& state, const Hand& sampled_hand,
                                            std::vector<double>& reach_probabilities, 
                                            int iteration, int player) {
    if (state.is_terminal()) {
        return state.get_payoffs();
    }
    
    int current_player = state.current_player;
    auto node = get_or_create_node(state, current_player);
    
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    if (actions.empty()) {
        return std::vector<double>(state.num_players, 0.0);
    }
    
    std::vector<double> strategy = node->get_strategy();
    
    if (current_player == player) {
        // Mettre à jour le joueur
        std::vector<double> action_values(actions.size());
        std::vector<double> node_values(state.num_players, 0.0);
        
        for (size_t i = 0; i < actions.size(); ++i) {
            GameState next_state = state.apply_action(actions[i]);
            std::vector<double> next_reach_probs = reach_probabilities;
            next_reach_probs[player] *= strategy[i];
            
            std::vector<double> action_result = mccfr(next_state, sampled_hand, 
                                                     next_reach_probs, iteration, player);
            action_values[i] = action_result[player];
            
            for (int p = 0; p < state.num_players; ++p) {
                node_values[p] += strategy[i] * action_result[p];
            }
        }
        
        // Calculer et mettre à jour les regrets
        std::vector<double> regrets(actions.size());
        for (size_t i = 0; i < actions.size(); ++i) {
            regrets[i] = action_values[i] - node_values[player];
        }
        node->update_regret(regrets);
        
        return node_values;
    } else {
        // Échantillonner une action pour les autres joueurs
        int sampled_action = sample_action(strategy);
        GameState next_state = state.apply_action(actions[sampled_action]);
        
        std::vector<double> next_reach_probs = reach_probabilities;
        next_reach_probs[current_player] *= strategy[sampled_action];
        
        return mccfr(next_state, sampled_hand, next_reach_probs, iteration, player);
    }
}

Hand ChanceSamplingCFR::sample_hand(const GameState& state) {
    auto cards = all_cards();
    
    // Enlever les cartes du board
    for (const Card& card : state.board) {
        cards.erase(std::remove(cards.begin(), cards.end(), card), cards.end());
    }
    
    // Échantillonner deux cartes
    std::shuffle(cards.begin(), cards.end(), rng_);
    if (cards.size() >= 2) {
        return {cards[0], cards[1]};
    }
    
    // Fallback
    return {Card("As"), Card("Kh")};
}

int ChanceSamplingCFR::sample_action(const std::vector<double>& strategy) {
    std::discrete_distribution<int> dist(strategy.begin(), strategy.end());
    return dist(rng_);
}

std::vector<double> ChanceSamplingCFR::get_strategy(const GameState& state, int player) const {
    // Même implémentation que VanillaCFR
    auto node = node_map_.find(state_to_key(state, player));
    if (node != node_map_.end()) {
        return node->second->get_average_strategy();
    }
    
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    if (actions.empty()) return {};
    
    return std::vector<double>(actions.size(), 1.0 / actions.size());
}

double ChanceSamplingCFR::calculate_exploitability(const GameState& root_state) const {
    // Utiliser la même implémentation complète que VanillaCFR
    if (root_state.num_players != 2) {
        std::cerr << "Avertissement: Calcul d'exploitabilité pour N>2 joueurs non standard (ChanceSamplingCFR)." << std::endl;
        return 0.01;
    }

    // Générer toutes les combinaisons de mains possibles pour les deux joueurs
    auto all_cards_vec = all_cards();
    std::vector<std::pair<Hand, Hand>> all_hand_pairs;
    
    // Générer toutes les paires de mains possibles (sans overlap)
    for (size_t i = 0; i < all_cards_vec.size(); ++i) {
        for (size_t j = i + 1; j < all_cards_vec.size(); ++j) {
            Hand hand1(all_cards_vec[i], all_cards_vec[j]);
            
            for (size_t k = 0; k < all_cards_vec.size(); ++k) {
                if (k == i || k == j) continue;
                
                for (size_t l = k + 1; l < all_cards_vec.size(); ++l) {
                    if (l == i || l == j) continue;
                    
                    Hand hand2(all_cards_vec[k], all_cards_vec[l]);
                    all_hand_pairs.emplace_back(hand1, hand2);
                }
            }
        }
    }
    
    if (all_hand_pairs.empty()) {
        return 0.01;
    }

    double total_exploitability = 0.0;
    
    // Calculer l'exploitabilité moyenne sur toutes les combinaisons de mains
    for (const auto& hand_pair : all_hand_pairs) {
        GameState current_state = root_state;
        current_state.player_hands = {hand_pair.first, hand_pair.second};
        
        // Calculer la valeur avec les stratégies actuelles
        double current_value_p0 = calculate_strategy_value(current_state, 0);
        double current_value_p1 = calculate_strategy_value(current_state, 1);
        
        // Calculer les valeurs de meilleure réponse
        double br_value_p0 = best_response_traversal(current_state, 0, {});
        double br_value_p1 = best_response_traversal(current_state, 1, {});
        
        // L'exploitabilité est la différence entre BR et stratégie actuelle
        double exploit_p0 = br_value_p0 - current_value_p0;
        double exploit_p1 = br_value_p1 - current_value_p1;
        
        total_exploitability += (exploit_p0 + exploit_p1) / 2.0;
    }
    
    return total_exploitability / all_hand_pairs.size();
}

// Fonction auxiliaire pour calculer la valeur avec la stratégie actuelle (partagée avec VanillaCFR)
double ChanceSamplingCFR::calculate_strategy_value(const GameState& state, int player) const {
    if (state.is_terminal()) {
        return state.get_payoffs()[player];
    }
    
    int current_player = state.current_player;
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    
    if (actions.empty()) {
        return state.get_payoffs()[player];
    }
    
    std::vector<double> strategy = get_strategy(state, current_player);
    
    double expected_value = 0.0;
    for (size_t i = 0; i < actions.size(); ++i) {
        GameState next_state = state.apply_action(actions[i]);
        double action_value = calculate_strategy_value(next_state, player);
        expected_value += strategy[i] * action_value;
    }
    
    return expected_value;
}

void ChanceSamplingCFR::save_checkpoint(const std::string& filename) const {
    std::ofstream file(filename, std::ios::binary);
    if (!file) {
        std::cerr << "Erreur: Impossible de sauvegarder le checkpoint MCCFR " << filename << std::endl;
        return;
    }
    
    // Sauvegarder l'itération actuelle
    file.write(reinterpret_cast<const char*>(&current_iteration_), sizeof(current_iteration_));
    
    // Sauvegarder l'état du générateur aléatoire
    std::ostringstream rng_state;
    rng_state << rng_;
    std::string rng_state_str = rng_state.str();
    size_t rng_state_size = rng_state_str.size();
    file.write(reinterpret_cast<const char*>(&rng_state_size), sizeof(rng_state_size));
    file.write(rng_state_str.c_str(), rng_state_size);
    
    // Sauvegarder le nombre de nœuds
    size_t num_nodes = node_map_.size();
    file.write(reinterpret_cast<const char*>(&num_nodes), sizeof(num_nodes));
    
    // Sauvegarder chaque nœud
    for (const auto& pair : node_map_) {
        const std::string& key = pair.first;
        const auto& node = pair.second;
        
        // Sauvegarder la clé
        size_t key_size = key.size();
        file.write(reinterpret_cast<const char*>(&key_size), sizeof(key_size));
        file.write(key.c_str(), key_size);
        
        // Sauvegarder les données du nœud
        size_t regret_size = node->regret_sum.size();
        file.write(reinterpret_cast<const char*>(&regret_size), sizeof(regret_size));
        file.write(reinterpret_cast<const char*>(node->regret_sum.data()), 
                   regret_size * sizeof(double));
        
        size_t strategy_size = node->strategy_sum.size();
        file.write(reinterpret_cast<const char*>(&strategy_size), sizeof(strategy_size));
        file.write(reinterpret_cast<const char*>(node->strategy_sum.data()), 
                   strategy_size * sizeof(double));
    }
    
    std::cout << "Checkpoint MCCFR sauvegardé: " << filename << std::endl;
}

void ChanceSamplingCFR::load_checkpoint(const std::string& filename) {
    std::ifstream file(filename, std::ios::binary);
    if (!file) {
        std::cerr << "Erreur: Impossible de charger le checkpoint MCCFR " << filename << std::endl;
        return;
    }
    
    // Charger l'itération
    file.read(reinterpret_cast<char*>(&current_iteration_), sizeof(current_iteration_));
    
    // Charger l'état du générateur aléatoire
    size_t rng_state_size;
    file.read(reinterpret_cast<char*>(&rng_state_size), sizeof(rng_state_size));
    std::string rng_state_str(rng_state_size, '\0');
    file.read(&rng_state_str[0], rng_state_size);
    std::istringstream rng_state_stream(rng_state_str);
    rng_state_stream >> rng_;
    
    // Charger le nombre de nœuds
    size_t num_nodes;
    file.read(reinterpret_cast<char*>(&num_nodes), sizeof(num_nodes));
    
    // Effacer les nœuds existants
    node_map_.clear();
    
    // Charger chaque nœud
    for (size_t i = 0; i < num_nodes; ++i) {
        // Charger la clé
        size_t key_size;
        file.read(reinterpret_cast<char*>(&key_size), sizeof(key_size));
        std::string key(key_size, '\0');
        file.read(&key[0], key_size);
        
        // Charger les données de regret
        size_t regret_size;
        file.read(reinterpret_cast<char*>(&regret_size), sizeof(regret_size));
        std::vector<double> regret_sum(regret_size);
        file.read(reinterpret_cast<char*>(regret_sum.data()), 
                  regret_size * sizeof(double));
        
        // Charger les données de stratégie
        size_t strategy_size;
        file.read(reinterpret_cast<char*>(&strategy_size), sizeof(strategy_size));
        std::vector<double> strategy_sum(strategy_size);
        file.read(reinterpret_cast<char*>(strategy_sum.data()), 
                  strategy_size * sizeof(double));
        
        // Reconstruire le GameNode
        try {
            GameState placeholder_state;
            placeholder_state.num_players = 2;
            
            auto node = std::make_shared<GameNode>(placeholder_state, 0);
            node->regret_sum = std::move(regret_sum);
            node->strategy_sum = std::move(strategy_sum);
            
            node_map_[key] = node;
            
        } catch (const std::exception& e) {
            std::cerr << "Erreur lors de la reconstruction du nœud MCCFR " << key 
                      << ": " << e.what() << std::endl;
        }
    }
    
    std::cout << "Checkpoint MCCFR chargé: " << filename << std::endl;
}

// CFRPlus implementation
CFRPlus::CFRPlus(std::shared_ptr<GameAbstraction> abstraction, const CFRConfig& config)
    : CFRSolver(abstraction, config) {}

CFRResult CFRPlus::solve(const GameState& initial_state) {
    // Implémentation similaire à VanillaCFR mais avec CFR+
    auto start_time = std::chrono::high_resolution_clock::now();
    
    CFRResult result;
    result.converged = false;
    
    std::vector<Hand> all_hands;
    auto cards = all_cards();
    for (size_t i = 0; i < cards.size(); ++i) {
        for (size_t j = i + 1; j < cards.size(); ++j) {
            all_hands.emplace_back(cards[i], cards[j]);
        }
    }
    
    for (int iteration = 1; iteration <= config_.max_iterations; ++iteration) {
        current_iteration_ = iteration;
        
        std::vector<double> reach_probs(initial_state.num_players, 1.0);
        std::vector<Hand> hands = all_hands;
        cfr_plus(initial_state, hands, reach_probs, iteration);
        
        if (iteration % 50 == 0) {
            double exploitability = calculate_exploitability(initial_state);
            std::cout << "CFR+ Iteration " << iteration << ": Exploitability = " 
                      << exploitability << std::endl;
            
            if (exploitability <= config_.target_exploitability) {
                result.converged = true;
                break;
            }
        }
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    
    result.iterations_completed = current_iteration_;
    result.final_exploitability = calculate_exploitability(initial_state);
    result.convergence_time_seconds = duration.count() / 1000.0;
    result.status_message = result.converged ? "Converged" : "Max iterations reached";
    
    return result;
}

std::vector<double> CFRPlus::cfr_plus(const GameState& state, std::vector<Hand>& hands,
                                     std::vector<double>& reach_probabilities, int iteration) {
    // Implémentation similaire à VanillaCFR mais avec regret matching +
    if (state.is_terminal()) {
        return state.get_payoffs();
    }
    
    int player = state.current_player;
    auto node = get_or_create_node(state, player);
    
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    if (actions.empty()) {
        return std::vector<double>(state.num_players, 0.0);
    }
    
    // Utiliser regret matching + pour la stratégie
    std::vector<double> strategy = regret_matching_plus(node->regret_sum);
    
    std::vector<double> action_values(actions.size());
    std::vector<double> node_values(state.num_players, 0.0);
    
    for (size_t i = 0; i < actions.size(); ++i) {
        GameState next_state = state.apply_action(actions[i]);
        std::vector<double> next_reach_probs = reach_probabilities;
        next_reach_probs[player] *= strategy[i];
        
        std::vector<double> action_result = cfr_plus(next_state, hands, next_reach_probs, iteration);
        action_values[i] = action_result[player];
        
        for (int p = 0; p < state.num_players; ++p) {
            node_values[p] += strategy[i] * action_result[p];
        }
    }
    
    // Calculer les regrets
    std::vector<double> regrets(actions.size());
    for (size_t i = 0; i < actions.size(); ++i) {
        regrets[i] = action_values[i] - node_values[player];
    }
    
    // CFR+: garder seulement les regrets positifs
    std::vector<double> positive_regrets(regrets.size());
    for (size_t i = 0; i < regrets.size(); ++i) {
        positive_regrets[i] = std::max(0.0, node->regret_sum[i] + regrets[i]);
    }
    node->regret_sum = positive_regrets;
    
    // Mettre à jour la somme des stratégies
    double reach_prob = reach_probabilities[player];
    std::vector<double> weighted_strategy(strategy.size());
    for (size_t i = 0; i < strategy.size(); ++i) {
        weighted_strategy[i] = reach_prob * strategy[i];
    }
    node->update_strategy_sum(weighted_strategy);
    
    return node_values;
}

std::vector<double> CFRPlus::regret_matching_plus(const std::vector<double>& regrets) const {
    std::vector<double> strategy(regrets.size());
    double positive_regret_sum = 0.0;
    
    for (size_t i = 0; i < regrets.size(); ++i) {
        strategy[i] = std::max(regrets[i], 0.0);
        positive_regret_sum += strategy[i];
    }
    
    if (positive_regret_sum > 0) {
        for (double& s : strategy) {
            s /= positive_regret_sum;
        }
    } else {
        std::fill(strategy.begin(), strategy.end(), 1.0 / strategy.size());
    }
    
    return strategy;
}

std::vector<double> CFRPlus::get_strategy(const GameState& state, int player) const {
    auto node = node_map_.find(state_to_key(state, player));
    if (node != node_map_.end()) {
        return node->second->get_average_strategy();
    }
    
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    if (actions.empty()) return {};
    
    return std::vector<double>(actions.size(), 1.0 / actions.size());
}

double CFRPlus::calculate_exploitability(const GameState& root_state) const {
    // Utiliser la même implémentation complète que VanillaCFR
    if (root_state.num_players != 2) {
        std::cerr << "Avertissement: Calcul d'exploitabilité pour N>2 joueurs non standard (CFRPlus)." << std::endl;
        return 0.01;
    }

    // Générer toutes les combinaisons de mains possibles pour les deux joueurs
    auto all_cards_vec = all_cards();
    std::vector<std::pair<Hand, Hand>> all_hand_pairs;
    
    // Générer toutes les paires de mains possibles (sans overlap)
    for (size_t i = 0; i < all_cards_vec.size(); ++i) {
        for (size_t j = i + 1; j < all_cards_vec.size(); ++j) {
            Hand hand1(all_cards_vec[i], all_cards_vec[j]);
            
            for (size_t k = 0; k < all_cards_vec.size(); ++k) {
                if (k == i || k == j) continue;
                
                for (size_t l = k + 1; l < all_cards_vec.size(); ++l) {
                    if (l == i || l == j) continue;
                    
                    Hand hand2(all_cards_vec[k], all_cards_vec[l]);
                    all_hand_pairs.emplace_back(hand1, hand2);
                }
            }
        }
    }
    
    if (all_hand_pairs.empty()) {
        return 0.01;
    }

    double total_exploitability = 0.0;
    
    // Calculer l'exploitabilité moyenne sur toutes les combinaisons de mains
    for (const auto& hand_pair : all_hand_pairs) {
        GameState current_state = root_state;
        current_state.player_hands = {hand_pair.first, hand_pair.second};
        
        // Calculer la valeur avec les stratégies actuelles
        double current_value_p0 = calculate_strategy_value(current_state, 0);
        double current_value_p1 = calculate_strategy_value(current_state, 1);
        
        // Calculer les valeurs de meilleure réponse
        double br_value_p0 = best_response_traversal(current_state, 0, {});
        double br_value_p1 = best_response_traversal(current_state, 1, {});
        
        // L'exploitabilité est la différence entre BR et stratégie actuelle
        double exploit_p0 = br_value_p0 - current_value_p0;
        double exploit_p1 = br_value_p1 - current_value_p1;
        
        total_exploitability += (exploit_p0 + exploit_p1) / 2.0;
    }
    
    return total_exploitability / all_hand_pairs.size();
}

// Fonction auxiliaire pour calculer la valeur avec la stratégie actuelle (partagée avec VanillaCFR)
double CFRPlus::calculate_strategy_value(const GameState& state, int player) const {
    if (state.is_terminal()) {
        return state.get_payoffs()[player];
    }
    
    int current_player = state.current_player;
    std::vector<Action> actions = abstraction_->get_abstracted_actions(state);
    
    if (actions.empty()) {
        return state.get_payoffs()[player];
    }
    
    std::vector<double> strategy = get_strategy(state, current_player);
    
    double expected_value = 0.0;
    for (size_t i = 0; i < actions.size(); ++i) {
        GameState next_state = state.apply_action(actions[i]);
        double action_value = calculate_strategy_value(next_state, player);
        expected_value += strategy[i] * action_value;
    }
    
    return expected_value;
}

void CFRPlus::save_checkpoint(const std::string& filename) const {
    std::ofstream file(filename, std::ios::binary);
    if (!file) {
        std::cerr << "Erreur: Impossible de sauvegarder le checkpoint CFR+ " << filename << std::endl;
        return;
    }
    
    // Sauvegarder l'itération actuelle
    file.write(reinterpret_cast<const char*>(&current_iteration_), sizeof(current_iteration_));
    
    // Sauvegarder le nombre de nœuds
    size_t num_nodes = node_map_.size();
    file.write(reinterpret_cast<const char*>(&num_nodes), sizeof(num_nodes));
    
    // Sauvegarder chaque nœud
    for (const auto& pair : node_map_) {
        const std::string& key = pair.first;
        const auto& node = pair.second;
        
        // Sauvegarder la clé
        size_t key_size = key.size();
        file.write(reinterpret_cast<const char*>(&key_size), sizeof(key_size));
        file.write(key.c_str(), key_size);
        
        // Sauvegarder les données du nœud (regret_sum pour CFR+ contient déjà les regrets positifs)
        size_t regret_size = node->regret_sum.size();
        file.write(reinterpret_cast<const char*>(&regret_size), sizeof(regret_size));
        file.write(reinterpret_cast<const char*>(node->regret_sum.data()), 
                   regret_size * sizeof(double));
        
        size_t strategy_size = node->strategy_sum.size();
        file.write(reinterpret_cast<const char*>(&strategy_size), sizeof(strategy_size));
        file.write(reinterpret_cast<const char*>(node->strategy_sum.data()), 
                   strategy_size * sizeof(double));
    }
    
    std::cout << "Checkpoint CFR+ sauvegardé: " << filename << std::endl;
}

void CFRPlus::load_checkpoint(const std::string& filename) {
    std::ifstream file(filename, std::ios::binary);
    if (!file) {
        std::cerr << "Erreur: Impossible de charger le checkpoint CFR+ " << filename << std::endl;
        return;
    }
    
    // Charger l'itération
    file.read(reinterpret_cast<char*>(&current_iteration_), sizeof(current_iteration_));
    
    // Charger le nombre de nœuds
    size_t num_nodes;
    file.read(reinterpret_cast<char*>(&num_nodes), sizeof(num_nodes));
    
    // Effacer les nœuds existants
    node_map_.clear();
    
    // Charger chaque nœud
    for (size_t i = 0; i < num_nodes; ++i) {
        // Charger la clé
        size_t key_size;
        file.read(reinterpret_cast<char*>(&key_size), sizeof(key_size));
        std::string key(key_size, '\0');
        file.read(&key[0], key_size);
        
        // Charger les données de regret
        size_t regret_size;
        file.read(reinterpret_cast<char*>(&regret_size), sizeof(regret_size));
        std::vector<double> regret_sum(regret_size);
        file.read(reinterpret_cast<char*>(regret_sum.data()), 
                  regret_size * sizeof(double));
        
        // Charger les données de stratégie
        size_t strategy_size;
        file.read(reinterpret_cast<char*>(&strategy_size), sizeof(strategy_size));
        std::vector<double> strategy_sum(strategy_size);
        file.read(reinterpret_cast<char*>(strategy_sum.data()), 
                  strategy_size * sizeof(double));
        
        // Reconstruire le GameNode
        try {
            GameState placeholder_state;
            placeholder_state.num_players = 2;
            
            auto node = std::make_shared<GameNode>(placeholder_state, 0);
            node->regret_sum = std::move(regret_sum);
            node->strategy_sum = std::move(strategy_sum);
            
            node_map_[key] = node;
            
        } catch (const std::exception& e) {
            std::cerr << "Erreur lors de la reconstruction du nœud CFR+ " << key 
                      << ": " << e.what() << std::endl;
        }
    }
    
    std::cout << "Checkpoint CFR+ chargé: " << filename << std::endl;
}

// Factory implementation
std::unique_ptr<CFRSolver> CFRSolverFactory::create_solver(
    SolverType type,
    std::shared_ptr<GameAbstraction> abstraction,
    const CFRConfig& config) {
    
    switch (type) {
        case SolverType::VANILLA_CFR:
            return std::make_unique<VanillaCFR>(abstraction, config);
        case SolverType::CHANCE_SAMPLING_CFR:
            return std::make_unique<ChanceSamplingCFR>(abstraction, config);
        case SolverType::CFR_PLUS:
            return std::make_unique<CFRPlus>(abstraction, config);
        default:
            return std::make_unique<VanillaCFR>(abstraction, config);
    }
}

} // namespace poker
