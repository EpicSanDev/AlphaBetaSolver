#include "game_tree.h"
#include "evaluator.h"
#include <sstream>
#include <algorithm>
#include <cmath>
#include <unordered_set> // Ajout pour std::unordered_set

namespace poker {

std::string Action::to_string() const {
    switch (type) {
        case ActionType::FOLD: return "FOLD";
        case ActionType::CHECK: return "CHECK";
        case ActionType::CALL: return "CALL";
        case ActionType::RAISE: return "RAISE(" + std::to_string(amount) + ")";
    }
    return "UNKNOWN";
}

bool Action::operator==(const Action& other) const {
    return type == other.type && 
           (type != ActionType::RAISE || std::abs(amount - other.amount) < 0.01);
}

std::vector<Action> GameState::get_legal_actions() const {
    std::vector<Action> actions;
    
    if (is_terminal()) return actions;
    
    double current_bet = *std::max_element(bets.begin(), bets.end());
    double player_bet = bets[current_player];
    double call_amount = current_bet - player_bet;
    double player_stack = stacks[current_player];
    
    // FOLD est toujours possible sauf si on peut checker
    if (call_amount > 0) {
        actions.push_back({ActionType::FOLD, 0});
    }
    
    // CHECK/CALL
    if (call_amount == 0) {
        actions.push_back({ActionType::CHECK, 0});
    } else if (call_amount <= player_stack) {
        actions.push_back({ActionType::CALL, call_amount});
    }
    
    // RAISE/BET
    double min_raise = current_bet * 2 - player_bet; // Minimum raise
    if (min_raise <= player_stack) {
        // Utiliser les tailles de mise autorisées
        for (double bet_size : allowed_bet_sizes) {
            double raise_amount = pot * bet_size;
            if (raise_amount >= min_raise && raise_amount <= player_stack) {
                actions.push_back({ActionType::RAISE, raise_amount});
            }
        }
        
        // All-in
        if (player_stack > min_raise) {
            actions.push_back({ActionType::RAISE, player_stack});
        }
    }
    
    return actions;
}

GameState GameState::apply_action(const Action& action) const {
    GameState new_state = *this;
    
    switch (action.type) {
        case ActionType::FOLD:
            new_state.folded_players[current_player] = true;
            // La logique pour déterminer si le tour/la main est terminée
            // ou pour passer au joueur suivant est gérée par la boucle de jeu
            // qui appellera is_terminal() et get_legal_actions().
            // Pour l'instant, on s'assure juste que le joueur est marqué comme couché.
            // On pourrait aussi directement passer au joueur suivant ici,
            // mais il faut s'assurer de sauter les joueurs déjà couchés.
            // Laissons la boucle de jeu principale gérer la transition pour l'instant.
            // Si tous les autres sauf un sont couchés, is_terminal() le détectera.
            break;
            
        case ActionType::CHECK:
            // Passer au joueur suivant
            new_state.current_player = (current_player + 1) % num_players;
            break;
            
        case ActionType::CALL:
            new_state.bets[current_player] = *std::max_element(bets.begin(), bets.end());
            new_state.stacks[current_player] -= action.amount;
            new_state.pot += action.amount;
            new_state.total_invested[current_player] += action.amount;
            new_state.current_player = (current_player + 1) % num_players;
            break;
            
        case ActionType::RAISE:
            new_state.bets[current_player] += action.amount; // Note: action.amount est le montant total de la relance, pas l'ajout
            // Il faudrait clarifier si action.amount pour RAISE est le montant total de la mise ou le montant ajouté.
            // En supposant que c'est le montant total de la mise pour ce tour:
            double amount_added_to_pot = action.amount - (new_state.bets[current_player] - bets[current_player]); // Ce qui était déjà misé par le joueur dans ce tour
            // Si action.amount est le montant à ajouter au bet précédent:
            // new_state.bets[current_player] = bets[current_player] + action.amount; // Ceci est incorrect si action.amount est le *nouveau* total bet
            // Supposons que action.amount est le montant total de la mise pour ce joueur pour ce tour.
            // La logique dans get_legal_actions pour RAISE semble calculer action.amount comme le montant à ajouter.
            // Clarification: Si RAISE(X), X est le montant total de la mise du joueur.
            // Donc, le montant ajouté au pot est X - new_state.bets[current_player] (avant la mise à jour).
            // Cependant, get_legal_actions semble générer 'amount' comme le montant à ajouter.
            // Pour être cohérent, si action.amount est le montant à ajouter:
            double previous_bet_this_street = new_state.bets[current_player]; // Bet du joueur avant cette action
            new_state.bets[current_player] += action.amount; // Le bet total du joueur pour ce street
            new_state.stacks[current_player] -= action.amount; // On retire le montant ajouté
            new_state.pot += action.amount; // On ajoute le montant ajouté au pot
            new_state.total_invested[current_player] += action.amount; // On ajoute le montant ajouté à l'investissement total
            new_state.current_player = (current_player + 1) % num_players;
            break;
    }
    
    return new_state;
}

bool GameState::is_terminal() const {
    // Terminal si un seul joueur reste ou si on a atteint la rivière et tous ont agi
    int active_players = 0;
    for (size_t i = 0; i < stacks.size(); ++i) {
        if (stacks[i] > 0 && !folded_players[i]) active_players++;
    }
    
    // Terminal si un seul joueur reste
    if (active_players <= 1) return true;
    
    // Terminal si on a atteint la rivière et tous les joueurs actifs ont agi
    if (street == 3) {
        double max_bet = *std::max_element(bets.begin(), bets.end());
        for (size_t i = 0; i < num_players; ++i) {
            if (!folded_players[i] && stacks[i] > 0 && bets[i] < max_bet) {
                return false; // Un joueur actif n'a pas encore égalisé
            }
        }
        return true;
    }
    
    return false;
}

std::vector<double> GameState::get_payoffs() const {
    std::vector<double> payoffs(num_players, 0.0);
    
    if (!is_terminal()) return payoffs;
    
    // Compter les joueurs actifs
    std::vector<int> active_players;
    for (size_t i = 0; i < num_players; ++i) {
        if (!folded_players[i] && stacks[i] >= 0) {
            active_players.push_back(i);
        }
    }
    
    if (active_players.size() == 1) {
        // Un seul joueur reste - il gagne tout le pot
        payoffs[active_players[0]] = pot;
    } else if (active_players.size() > 1) {
        // Showdown - utiliser l'évaluateur pour déterminer le gagnant
        int winner = determine_winner(active_players);
        if (winner >= 0) {
            payoffs[winner] = pot;
        } else {
            // Égalité - partager le pot
            double share = pot / active_players.size();
            for (int player : active_players) {
                payoffs[player] = share;
            }
        }
    }
    
    // Les payoffs sont calculés par rapport à ce qui a été misé DANS CE POT.
    // Si un joueur gagne le pot, son payoff est pot - son_investissement_dans_ce_pot.
    // total_invested devrait refléter l'investissement total depuis le début de la main.
    // La logique de get_payoffs semble correcte si total_invested est bien l'investissement total.
    // Le pot contient déjà toutes les mises. Si un joueur gagne le pot, il reçoit 'pot'.
    // Son gain net est 'pot - ce_qu_il_a_misé_dans_la_main_entiere'.
    // Cependant, dans CFR, les payoffs sont souvent relatifs à l'état de départ du noeud.
    // Pour l'instant, laissons comme c'est, en assumant que total_invested est correct.
    // Si payoffs[winner] = pot, alors le gain net est pot - total_invested[winner].
    // Si on partage, payoffs[player] = share, gain net share - total_invested[player].
    // Cela semble être la convention.

    // La soustraction de total_invested est déjà là, donc c'est bon.
    for (size_t i = 0; i < num_players; ++i) {
        payoffs[i] -= total_invested[i];
    }
    
    return payoffs;
}

double GameState::get_effective_stack() const {
    if (stacks.empty()) return 0.0;
    return *std::min_element(stacks.begin(), stacks.end());
}

std::string GameState::to_string() const {
    std::ostringstream oss;
    oss << "GameState{";
    oss << "board=" << board_to_string(board);
    oss << ", pot=" << pot;
    oss << ", street=" << street;
    oss << ", current_player=" << current_player;
    oss << ", folded=[";
    for(size_t i=0; i < folded_players.size(); ++i) {
        oss << folded_players[i] << (i == folded_players.size()-1 ? "" : ",");
    }
    oss << "]";
    oss << "}";
    return oss.str();
}

// Implémentation de determine_winner
// Suppose que evaluator.h fournit HandStrength evaluate_hand(const Hand& hand, const Board& board);
// et que HandStrength est comparable (plus grand est meilleur).
int GameState::determine_winner(const std::vector<int>& active_player_indices) const {
    if (active_player_indices.empty()) {
        return -1; // Pas de joueurs actifs
    }
    if (active_player_indices.size() == 1) {
        return active_player_indices[0]; // Un seul joueur actif gagne
    }

    int best_player_idx = -1;
    HandStrength best_strength; // Supposons un constructeur par défaut ou une valeur minimale

    // Nécessite l'accès à un évaluateur de mains
    // Pour l'instant, nous allons simuler cela.
    // Idéalement, cela proviendrait de #include "evaluator.h"
    // et d'une fonction comme `HandEvaluator::evaluate(const Hand& hand, const Board& board)`
    // qui retourne une structure ou un int comparable.

    // Simulation simple: le premier joueur actif gagne toujours (placeholder)
    // return active_player_indices[0]; 
    // Pour une vraie implémentation, il faudrait:

    bool first = true;
    for (int player_idx : active_player_indices) {
        if (player_idx < 0 || player_idx >= num_players) continue; // Index invalide

        // Assurez-vous que player_hands est rempli correctement ailleurs dans le code.
        // La vérification de validité de la main est implicitement gérée par la logique qui peuple active_player_indices.
        // Si un joueur est actif, sa main doit être considérée comme valide pour l'évaluation.
        // if (player_hands.empty() || player_hands[player_idx].first.is_unknown() || player_hands[player_idx].second.is_unknown()) {
        //     // Main non valide ou non définie pour ce joueur
        //     continue;
        // }

        std::vector<Card> cards_to_evaluate = board;
        cards_to_evaluate.push_back(player_hands[player_idx].first);
        cards_to_evaluate.push_back(player_hands[player_idx].second);
        
        HandStrength current_strength = HandEvaluator::evaluate(cards_to_evaluate);
        
        if (first || current_strength > best_strength) {
            best_strength = current_strength;
            best_player_idx = player_idx;
            first = false;
        } else if (current_strength == best_strength) {
            // Gérer l'égalité (split pot)
            // Pour CFR, on peut retourner -1 pour indiquer un split,
            // et get_payoffs s'en chargera.
            best_player_idx = -2; // Code spécial pour égalité multiple
        }
    }
    if (best_player_idx == -2) return -1; // Indiquer égalité pour get_payoffs
    return best_player_idx;
}


// GameNode implementation
GameNode::GameNode(const GameState& state, int player) 
    : state_(state), player_(player) {
    
    if (!is_terminal()) {
        actions = state_.get_legal_actions();
        regret_sum.resize(actions.size(), 0.0);
        strategy_sum.resize(actions.size(), 0.0);
    }
}

std::vector<double> GameNode::get_strategy() const {
    std::vector<double> strategy(actions.size());
    double normalizing_sum = 0.0;
    
    for (size_t i = 0; i < actions.size(); ++i) {
        strategy[i] = std::max(regret_sum[i], 0.0);
        normalizing_sum += strategy[i];
    }
    
    if (normalizing_sum > 0) {
        for (double& s : strategy) {
            s /= normalizing_sum;
        }
    } else {
        // Stratégie uniforme si aucun regret positif
        std::fill(strategy.begin(), strategy.end(), 1.0 / actions.size());
    }
    
    return strategy;
}

std::vector<double> GameNode::get_average_strategy() const {
    std::vector<double> avg_strategy(actions.size());
    double normalizing_sum = 0.0;
    
    for (size_t i = 0; i < actions.size(); ++i) {
        normalizing_sum += strategy_sum[i];
    }
    
    if (normalizing_sum > 0) {
        for (size_t i = 0; i < actions.size(); ++i) {
            avg_strategy[i] = strategy_sum[i] / normalizing_sum;
        }
    } else {
        std::fill(avg_strategy.begin(), avg_strategy.end(), 1.0 / actions.size());
    }
    
    return avg_strategy;
}

void GameNode::update_regret(const std::vector<double>& regret) {
    for (size_t i = 0; i < regret_sum.size() && i < regret.size(); ++i) {
        regret_sum[i] += regret[i];
    }
}

void GameNode::update_strategy_sum(const std::vector<double>& strategy) {
    for (size_t i = 0; i < strategy_sum.size() && i < strategy.size(); ++i) {
        strategy_sum[i] += strategy[i];
    }
}

// BasicAbstraction implementation
BasicAbstraction::BasicAbstraction() : num_preflop_buckets_(169) {
    initialize_preflop_bucketing();
}

void BasicAbstraction::initialize_preflop_bucketing() {
    // Créer les 169 mains préflop possibles (13*13 matrix)
    std::vector<std::string> ranks = {"2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"};
    
    int bucket = 0;
    for (int i = 0; i < 13; ++i) {
        for (int j = 0; j < 13; ++j) {
            std::string hand_str;
            if (i == j) {
                // Paire
                hand_str = ranks[i] + ranks[j];
            } else if (i < j) {
                // Suited
                hand_str = ranks[j] + ranks[i] + "s";
            } else {
                // Offsuit
                hand_str = ranks[i] + ranks[j] + "o";
            }
            preflop_hand_to_bucket_[hand_str] = bucket++;
        }
    }
}

int BasicAbstraction::get_hand_bucket(const Hand& hand, const Board& board) const {
    if (board.empty()) {
        // Préflop - utiliser le bucketing préflop
        return classify_preflop_hand(hand);
    } else {
        // Postflop - utiliser l'équité
        // 1. Définir une range adverse simplifiée (toutes les mains possibles non conflictuelles)
        std::vector<Card> all_deck_cards = all_cards();
        std::unordered_set<Card> known_cards_set;
        known_cards_set.insert(hand.first);
        known_cards_set.insert(hand.second);
        for (const Card& c : board) {
            known_cards_set.insert(c);
        }

        std::vector<Card> remaining_deck;
        for (const Card& c : all_deck_cards) {
            if (known_cards_set.find(c) == known_cards_set.end()) {
                remaining_deck.push_back(c);
            }
        }

        std::vector<Hand> opponent_range;
        if (remaining_deck.size() >= 2) {
            for (size_t i = 0; i < remaining_deck.size(); ++i) {
                for (size_t j = i + 1; j < remaining_deck.size(); ++j) {
                    opponent_range.push_back({remaining_deck[i], remaining_deck[j]});
                }
            }
        }
        
        // Si la range adverse est vide (ne devrait pas arriver avec un deck standard),
        // retourner un bucket par défaut ou gérer l'erreur.
        if (opponent_range.empty()) {
             // Pourrait arriver si le board + main du joueur = 7 cartes, ne laissant pas assez pour une main adverse.
             // Dans ce cas, l'équité est triviale (100% ou 0% si on pouvait déterminer le gagnant).
             // Retournons un bucket moyen pour l'instant.
            return num_preflop_buckets_ + 5; // Exemple de bucket postflop moyen
        }

        // 2. Calculer l'équité
        // Utiliser un nombre plus faible de simulations pour la performance du bucketing.
        double equity = HandEvaluator::monte_carlo_equity(hand, opponent_range, board, 1000); 

        // 3. Mapper l'équité à un bucket (par exemple, 10 buckets postflop)
        const int num_postflop_buckets = 10;
        int bucket_index = static_cast<int>(equity * num_postflop_buckets);
        if (bucket_index >= num_postflop_buckets) { // Pour equity = 1.0
            bucket_index = num_postflop_buckets - 1;
        }
        
        // Les buckets postflop commencent après les buckets préflop
        return num_preflop_buckets_ + bucket_index;
    }
}

int BasicAbstraction::classify_preflop_hand(const Hand& hand) const {
    std::string hand_str;
    Card c1 = hand.first, c2 = hand.second;
    
    // Assurer l'ordre: carte la plus haute en premier
    if (c1.rank() < c2.rank()) {
        std::swap(c1, c2);
    }
    
    char rank1 = static_cast<char>('2' + static_cast<int>(c1.rank()) - 2);
    char rank2 = static_cast<char>('2' + static_cast<int>(c2.rank()) - 2);
    
    if (rank1 == '1') rank1 = 'T'; // Pour 10
    if (rank2 == '1') rank2 = 'T';
    if (rank1 == ':') rank1 = 'J'; // Pour Jack (11)
    if (rank2 == ':') rank2 = 'J';
    if (rank1 == ';') rank1 = 'Q'; // Pour Queen (12)
    if (rank2 == ';') rank2 = 'Q';
    if (rank1 == '<') rank1 = 'K'; // Pour King (13)
    if (rank2 == '<') rank2 = 'K';
    if (rank1 == '=') rank1 = 'A'; // Pour Ace (14)
    if (rank2 == '=') rank2 = 'A';
    
    if (c1.rank() == c2.rank()) {
        hand_str = std::string(1, rank1) + std::string(1, rank2);
    } else if (c1.suit() == c2.suit()) {
        hand_str = std::string(1, rank1) + std::string(1, rank2) + "s";
    } else {
        hand_str = std::string(1, rank1) + std::string(1, rank2) + "o";
    }
    
    auto it = preflop_hand_to_bucket_.find(hand_str);
    return (it != preflop_hand_to_bucket_.end()) ? it->second : 0;
}

std::vector<Action> BasicAbstraction::get_abstracted_actions(const GameState& state) const {
    std::vector<Action> all_actions = state.get_legal_actions();
    std::vector<Action> abstracted;
    
    std::vector<Action> raise_actions;
    bool has_all_in = false;
    Action all_in_action;

    for (const Action& action : all_actions) {
        if (action.type == ActionType::FOLD || 
            action.type == ActionType::CHECK || 
            action.type == ActionType::CALL) {
            abstracted.push_back(action);
        } else if (action.type == ActionType::RAISE) {
            // Vérifier si c'est un all-in (montant égal au stack du joueur)
            // Note: nécessite l'accès au stack du joueur, qui n'est pas directement ici.
            // On peut supposer que la dernière action de raise dans get_legal_actions est all-in si elle est plus grande.
            // Pour une meilleure logique, get_legal_actions devrait marquer l'action all-in.
            // Simplification: on considère le raise le plus élevé comme un potentiel all-in.
            raise_actions.push_back(action);
        }
    }

    if (!raise_actions.empty()) {
        std::sort(raise_actions.begin(), raise_actions.end(), 
                  [](const Action& a, const Action& b) { return a.amount < b.amount; });

        // Garder la plus petite mise (si elle existe et n'est pas all-in)
        abstracted.push_back(raise_actions.front());

        // Garder la plus grosse mise (potentiellement all-in) si différente de la plus petite
        if (raise_actions.size() > 1 && raise_actions.back().amount > raise_actions.front().amount) {
            abstracted.push_back(raise_actions.back());
        }
        // On pourrait aussi ajouter une mise "moyenne" si plus de 2 options de raise existent.
        // Par exemple, si 3 raises ou plus (non all-in), prendre celle du milieu.
        if (raise_actions.size() >= 3) {
            // Tentative de trouver une mise "moyenne" distincte des extrêmes
            Action middle_raise = raise_actions[raise_actions.size() / 2];
            bool smallest_is_different = middle_raise.amount > raise_actions.front().amount;
            bool largest_is_different = middle_raise.amount < raise_actions.back().amount;
            if (smallest_is_different && largest_is_different) {
                 // S'assurer qu'on n'ajoute pas une action déjà présente (si seulement 2 raises au total)
                bool already_added = false;
                for(const auto& act : abstracted) {
                    if(act.type == ActionType::RAISE && std::abs(act.amount - middle_raise.amount) < 0.01) {
                        already_added = true;
                        break;
                    }
                }
                if(!already_added) {
                    abstracted.push_back(middle_raise);
                }
            }
        }
    }
    // S'assurer qu'il n'y a pas de doublons exacts (même si peu probable avec cette logique)
    std::sort(abstracted.begin(), abstracted.end(), [](const Action&a, const Action&b){
        if(a.type != b.type) return a.type < b.type;
        return a.amount < b.amount;
    });
    abstracted.erase(std::unique(abstracted.begin(), abstracted.end()), abstracted.end());

    return abstracted;
}

int BasicAbstraction::get_board_isomorphism_class(const Board& board) const {
    // Simplification: tous les boards de même street sont dans la même classe
    // TODO: Implémenter un isomorphisme plus fin (ex: basé sur la texture du board)
    // Exemple d'amélioration simple : street + indication de board pairé
    int base_class = static_cast<int>(board.size()); // 0, 3, 4, 5

    if (board.size() >= 2) { // Au moins deux cartes pour vérifier une paire
        std::vector<Rank> ranks;
        for(const auto& card : board) {
            ranks.push_back(card.rank());
        }
        std::sort(ranks.begin(), ranks.end());
        bool paired = false;
        for(size_t i = 0; i < ranks.size() - 1; ++i) {
            if (ranks[i] == ranks[i+1]) {
                paired = true;
                break;
            }
        }
        if (paired) {
            return base_class + 10; // Classe distincte pour les boards pairés (ex: 13 pour flop pairé)
        }
    }
    // On pourrait ajouter d'autres modificateurs pour les tirages couleur, etc.
    // Par exemple, +20 pour board monochrome, +30 pour tirage quinte évident, etc.
    return base_class;
}

} // namespace poker
