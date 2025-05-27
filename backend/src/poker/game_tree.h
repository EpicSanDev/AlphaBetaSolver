#pragma once

#include "card.h"
#include <vector>
#include <memory>
#include <string>
#include <unordered_map>

namespace poker {

enum class ActionType {
    FOLD = 0,
    CHECK = 1,
    CALL = 2,
    RAISE = 3
};

struct Action {
    ActionType type;
    double amount; // Montant de la mise (pour RAISE)
    
    std::string to_string() const;
    bool operator==(const Action& other) const;
};

enum class Position {
    SMALL_BLIND = 0,
    BIG_BLIND = 1,
    EARLY = 2,
    MIDDLE = 3,
    LATE = 4,
    BUTTON = 5
};

struct GameState {
    Board board;
    std::vector<Hand> player_hands;  // Mains des joueurs
    std::vector<double> stacks;      // Tailles de stack de chaque joueur
    std::vector<double> bets;        // Mises actuelles de chaque joueur
    double pot;
    int current_player;
    int button_position;
    int num_players;
    int street; // 0=preflop, 1=flop, 2=turn, 3=river
    std::vector<bool> folded_players; // True si le joueur s'est couché
    std::vector<double> total_invested; // Montant total investi par chaque joueur dans la main
    
    // Configuration du jeu
    double small_blind;
    double big_blind;
    std::vector<double> allowed_bet_sizes; // En pourcentage du pot: 0.33, 0.5, 0.75, 1.0, etc.
    
    std::vector<Action> get_legal_actions() const;
    GameState apply_action(const Action& action) const;
    bool is_terminal() const;
    std::vector<double> get_payoffs() const; // Gains finaux pour chaque joueur
    double get_effective_stack() const; // Plus petite stack effective
    int determine_winner(const std::vector<int>& active_players) const; // Détermine le gagnant parmi les joueurs actifs
    
    std::string to_string() const;

    // Constructeur par défaut pour initialiser les vecteurs
    GameState() : num_players(0), pot(0.0), current_player(0), button_position(0), street(0), small_blind(0), big_blind(0) {}

    // Constructeur pour initialiser avec le nombre de joueurs
    GameState(int n_players) : 
        num_players(n_players),
        player_hands(n_players), // Initialiser avec des mains vides
        stacks(n_players, 0.0), 
        bets(n_players, 0.0), 
        folded_players(n_players, false), 
        total_invested(n_players, 0.0),
        pot(0.0), 
        current_player(0), 
        button_position(0), 
        street(0), 
        small_blind(0), 
        big_blind(0) {}
};

// Nœud dans l'arbre de jeu pour CFR
class GameNode {
public:
    GameNode(const GameState& state, int player);
    
    const GameState& get_state() const { return state_; }
    int get_player() const { return player_; }
    bool is_chance_node() const { return player_ == -1; }
    bool is_terminal() const { return state_.is_terminal(); }
    
    // Pour CFR
    std::vector<double> regret_sum;
    std::vector<double> strategy_sum;
    std::vector<Action> actions;
    
    std::vector<double> get_strategy() const;
    std::vector<double> get_average_strategy() const;
    void update_regret(const std::vector<double>& regret);
    void update_strategy_sum(const std::vector<double>& strategy);
    
private:
    GameState state_;
    int player_; // -1 pour les nœuds de chance (distribution de cartes)
};

// Générateur d'abstraction pour simplifier l'arbre de jeu
class GameAbstraction {
public:
    virtual ~GameAbstraction() = default;
    
    // Abstraction des cartes (bucketing)
    virtual int get_hand_bucket(const Hand& hand, const Board& board) const = 0;
    virtual int get_num_hand_buckets() const = 0;
    
    // Abstraction des actions
    virtual std::vector<Action> get_abstracted_actions(const GameState& state) const = 0;
    
    // Isomorphisme des boards
    virtual int get_board_isomorphism_class(const Board& board) const = 0;
};

// Implémentation basique d'abstraction
class BasicAbstraction : public GameAbstraction {
public:
    BasicAbstraction();
    
    int get_hand_bucket(const Hand& hand, const Board& board) const override;
    int get_num_hand_buckets() const override { return num_preflop_buckets_; }
    
    std::vector<Action> get_abstracted_actions(const GameState& state) const override;
    int get_board_isomorphism_class(const Board& board) const override;
    
private:
    int num_preflop_buckets_;
    std::unordered_map<std::string, int> preflop_hand_to_bucket_;
    
    void initialize_preflop_bucketing();
    int classify_preflop_hand(const Hand& hand) const;
};

} // namespace poker
