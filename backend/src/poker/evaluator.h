#pragma once

#include "card.h"
#include <vector>
#include <array>

namespace poker {

enum class HandRanking : uint8_t {
    HIGH_CARD = 0,
    PAIR = 1,
    TWO_PAIR = 2,
    THREE_OF_A_KIND = 3,
    STRAIGHT = 4,
    FLUSH = 5,
    FULL_HOUSE = 6,
    FOUR_OF_A_KIND = 7,
    STRAIGHT_FLUSH = 8
};

struct HandStrength {
    HandRanking ranking;
    std::array<uint8_t, 5> kickers; // Pour départager les égalités
    
    bool operator>(const HandStrength& other) const;
    bool operator==(const HandStrength& other) const;
    std::string to_string() const;
};

class HandEvaluator {
public:
    // Évalue une main de 5, 6 ou 7 cartes et retourne la meilleure main de 5 cartes
    static HandStrength evaluate(const std::vector<Card>& cards);
    
    // Évalue spécifiquement 5 cartes
    static HandStrength evaluate_five_cards(const std::vector<Card>& cards);
    
    // Calcule l'équité d'une main contre une range sur un board donné
    static double calculate_equity(const Hand& hand, const std::vector<Hand>& opponent_range, 
                                   const Board& board);
    
    // Simule N tirages aléatoires pour calculer l'équité (Monte Carlo)
    static double monte_carlo_equity(const Hand& hand, const std::vector<Hand>& opponent_range,
                                     const Board& board, int simulations = 10000);

private:
    static bool is_flush(const std::vector<Card>& cards);
    static bool is_straight(const std::vector<Card>& cards);
    static std::vector<uint8_t> get_rank_counts(const std::vector<Card>& cards);
    static HandStrength evaluate_with_counts(const std::vector<Card>& cards, 
                                              const std::vector<uint8_t>& rank_counts);
};

} // namespace poker
