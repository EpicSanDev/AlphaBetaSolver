#include "evaluator.h"
#include <algorithm>
#include <unordered_set>
#include <random>
#include <set>
#include <stdexcept>

namespace poker {

bool HandStrength::operator>(const HandStrength& other) const {
    if (ranking != other.ranking) {
        return ranking > other.ranking;
    }
    
    for (size_t i = 0; i < kickers.size(); ++i) {
        if (kickers[i] != other.kickers[i]) {
            return kickers[i] > other.kickers[i];
        }
    }
    
    return false; // Égalité
}

bool HandStrength::operator==(const HandStrength& other) const {
    return ranking == other.ranking && kickers == other.kickers;
}

std::string HandStrength::to_string() const {
    const char* ranking_names[] = {
        "High Card", "Pair", "Two Pair", "Three of a Kind", "Straight",
        "Flush", "Full House", "Four of a Kind", "Straight Flush"
    };
    return ranking_names[static_cast<int>(ranking)];
}

HandStrength HandEvaluator::evaluate(const std::vector<Card>& cards) {
    if (cards.size() < 5 || cards.size() > 7) {
        throw std::invalid_argument("Hand evaluation requires 5-7 cards");
    }
    
    if (cards.size() == 5) {
        return evaluate_five_cards(cards);
    }
    
    // Pour 6 ou 7 cartes, tester toutes les combinaisons de 5 cartes
    HandStrength best_hand;
    best_hand.ranking = HandRanking::HIGH_CARD;
    
    std::vector<size_t> indices(cards.size());
    std::iota(indices.begin(), indices.end(), 0);
    
    std::vector<bool> selector(cards.size());
    std::fill(selector.end() - 5, selector.end(), true);
    
    do {
        std::vector<Card> five_cards;
        for (size_t i = 0; i < cards.size(); ++i) {
            if (selector[i]) {
                five_cards.push_back(cards[i]);
            }
        }
        
        HandStrength current = evaluate_five_cards(five_cards);
        if (current > best_hand) {
            best_hand = current;
        }
    } while (std::next_permutation(selector.begin(), selector.end()));
    
    return best_hand;
}

HandStrength HandEvaluator::evaluate_five_cards(const std::vector<Card>& cards) {
    if (cards.size() != 5) {
        throw std::invalid_argument("evaluate_five_cards requires exactly 5 cards");
    }
    
    std::vector<uint8_t> rank_counts = get_rank_counts(cards);
    return evaluate_with_counts(cards, rank_counts);
}

bool HandEvaluator::is_flush(const std::vector<Card>& cards) {
    Suit first_suit = cards[0].suit();
    return std::all_of(cards.begin(), cards.end(), 
                       [first_suit](const Card& c) { return c.suit() == first_suit; });
}

bool HandEvaluator::is_straight(const std::vector<Card>& cards) {
    std::vector<uint8_t> ranks;
    for (const Card& card : cards) {
        ranks.push_back(static_cast<uint8_t>(card.rank()));
    }
    std::sort(ranks.begin(), ranks.end());
    
    // Vérifier la séquence normale
    bool normal_straight = true;
    for (size_t i = 1; i < ranks.size(); ++i) {
        if (ranks[i] != ranks[i-1] + 1) {
            normal_straight = false;
            break;
        }
    }
    
    if (normal_straight) return true;
    
    // Vérifier la quinte A-2-3-4-5 (wheel)
    if (ranks.size() == 5 && ranks[0] == 2 && ranks[1] == 3 && 
        ranks[2] == 4 && ranks[3] == 5 && ranks[4] == 14) {
        return true;
    }
    
    return false;
}

std::vector<uint8_t> HandEvaluator::get_rank_counts(const std::vector<Card>& cards) {
    std::vector<uint8_t> counts(15, 0); // Index 2-14 pour les rangs
    
    for (const Card& card : cards) {
        counts[static_cast<uint8_t>(card.rank())]++;
    }
    
    return counts;
}

HandStrength HandEvaluator::evaluate_with_counts(const std::vector<Card>& cards, 
                                                  const std::vector<uint8_t>& rank_counts) {
    HandStrength result;
    std::fill(result.kickers.begin(), result.kickers.end(), 0);
    
    bool flush = is_flush(cards);
    bool straight = is_straight(cards);
    
    // Compter les paires, brelans, etc.
    std::vector<uint8_t> pairs, trips, quads;
    for (uint8_t rank = 2; rank <= 14; ++rank) {
        if (rank_counts[rank] == 2) pairs.push_back(rank);
        else if (rank_counts[rank] == 3) trips.push_back(rank);
        else if (rank_counts[rank] == 4) quads.push_back(rank);
    }
    
    // Déterminer le type de main
    if (straight && flush) {
        result.ranking = HandRanking::STRAIGHT_FLUSH;
        // Pour les kickers d'une quinte, utiliser la carte la plus haute
        std::vector<uint8_t> ranks;
        for (const Card& card : cards) {
            ranks.push_back(static_cast<uint8_t>(card.rank()));
        }
        std::sort(ranks.rbegin(), ranks.rend());
        result.kickers[0] = ranks[0];
    }
    else if (!quads.empty()) {
        result.ranking = HandRanking::FOUR_OF_A_KIND;
        result.kickers[0] = quads[0];
        // Trouver la cinquième carte
        for (uint8_t rank = 14; rank >= 2; --rank) {
            if (rank_counts[rank] == 1) {
                result.kickers[1] = rank;
                break;
            }
        }
    }
    else if (!trips.empty() && !pairs.empty()) {
        result.ranking = HandRanking::FULL_HOUSE;
        result.kickers[0] = trips[0];
        result.kickers[1] = pairs.back(); // La paire la plus haute
    }
    else if (flush) {
        result.ranking = HandRanking::FLUSH;
        // Toutes les cartes en ordre décroissant
        std::vector<uint8_t> ranks;
        for (const Card& card : cards) {
            ranks.push_back(static_cast<uint8_t>(card.rank()));
        }
        std::sort(ranks.rbegin(), ranks.rend());
        for (size_t i = 0; i < 5 && i < ranks.size(); ++i) {
            result.kickers[i] = ranks[i];
        }
    }
    else if (straight) {
        result.ranking = HandRanking::STRAIGHT;
        std::vector<uint8_t> ranks;
        for (const Card& card : cards) {
            ranks.push_back(static_cast<uint8_t>(card.rank()));
        }
        std::sort(ranks.rbegin(), ranks.rend());
        result.kickers[0] = ranks[0];
    }
    else if (!trips.empty()) {
        result.ranking = HandRanking::THREE_OF_A_KIND;
        result.kickers[0] = trips[0];
        // Deux cartes restantes
        std::vector<uint8_t> remaining;
        for (uint8_t rank = 14; rank >= 2; --rank) {
            if (rank_counts[rank] == 1) {
                remaining.push_back(rank);
            }
        }
        for (size_t i = 0; i < 2 && i < remaining.size(); ++i) {
            result.kickers[i + 1] = remaining[i];
        }
    }
    else if (pairs.size() >= 2) {
        result.ranking = HandRanking::TWO_PAIR;
        std::sort(pairs.rbegin(), pairs.rend());
        result.kickers[0] = pairs[0];
        result.kickers[1] = pairs[1];
        // Cinquième carte
        for (uint8_t rank = 14; rank >= 2; --rank) {
            if (rank_counts[rank] == 1) {
                result.kickers[2] = rank;
                break;
            }
        }
    }
    else if (pairs.size() == 1) {
        result.ranking = HandRanking::PAIR;
        result.kickers[0] = pairs[0];
        // Trois cartes restantes
        std::vector<uint8_t> remaining;
        for (uint8_t rank = 14; rank >= 2; --rank) {
            if (rank_counts[rank] == 1) {
                remaining.push_back(rank);
            }
        }
        for (size_t i = 0; i < 3 && i < remaining.size(); ++i) {
            result.kickers[i + 1] = remaining[i];
        }
    }
    else {
        result.ranking = HandRanking::HIGH_CARD;
        std::vector<uint8_t> ranks;
        for (const Card& card : cards) {
            ranks.push_back(static_cast<uint8_t>(card.rank()));
        }
        std::sort(ranks.rbegin(), ranks.rend());
        for (size_t i = 0; i < 5 && i < ranks.size(); ++i) {
            result.kickers[i] = ranks[i];
        }
    }
    
    return result;
}

double HandEvaluator::calculate_equity(const Hand& hand, const std::vector<Hand>& opponent_range, 
                                       const Board& board) {
    // Version simplifiée pour le moment - utilise Monte Carlo
    return monte_carlo_equity(hand, opponent_range, board, 10000);
}

double HandEvaluator::monte_carlo_equity(const Hand& hand, const std::vector<Hand>& opponent_range,
                                         const Board& board, int simulations) {
    if (opponent_range.empty()) return 1.0;
    
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> range_dist(0, opponent_range.size() - 1);
    
    // Cartes déjà utilisées
    std::unordered_set<Card> used_cards;
    used_cards.insert(hand.first);
    used_cards.insert(hand.second);
    for (const Card& card : board) {
        used_cards.insert(card);
    }
    
    // Cartes disponibles pour compléter le board
    std::vector<Card> deck = all_cards();
    deck.erase(std::remove_if(deck.begin(), deck.end(), 
                              [&used_cards](const Card& c) { 
                                  return used_cards.find(c) != used_cards.end(); 
                              }), deck.end());
    
    int wins = 0;
    int ties = 0;
    
    for (int i = 0; i < simulations; ++i) {
        // Choisir une main adverse aléatoirement
        Hand opponent_hand = opponent_range[range_dist(gen)];
        
        // Vérifier que les cartes ne se chevauchent pas
        if (opponent_hand.first == hand.first || opponent_hand.first == hand.second ||
            opponent_hand.second == hand.first || opponent_hand.second == hand.second) {
            continue; // Conflit de cartes, ignorer cette simulation
        }
        
        // Compléter le board si nécessaire
        Board complete_board = board;
        std::vector<Card> available_deck = deck;
        available_deck.erase(std::remove(available_deck.begin(), available_deck.end(), opponent_hand.first), available_deck.end());
        available_deck.erase(std::remove(available_deck.begin(), available_deck.end(), opponent_hand.second), available_deck.end());
        
        std::shuffle(available_deck.begin(), available_deck.end(), gen);
        
        // Ajouter des cartes pour compléter le board jusqu'à 5 cartes
        while (complete_board.size() < 5 && !available_deck.empty()) {
            complete_board.push_back(available_deck.back());
            available_deck.pop_back();
        }
        
        if (complete_board.size() != 5) continue;
        
        // Évaluer les deux mains
        std::vector<Card> our_cards = {hand.first, hand.second};
        our_cards.insert(our_cards.end(), complete_board.begin(), complete_board.end());
        
        std::vector<Card> opp_cards = {opponent_hand.first, opponent_hand.second};
        opp_cards.insert(opp_cards.end(), complete_board.begin(), complete_board.end());
        
        HandStrength our_strength = evaluate(our_cards);
        HandStrength opp_strength = evaluate(opp_cards);
        
        if (our_strength > opp_strength) {
            wins++;
        } else if (our_strength == opp_strength) {
            ties++;
        }
    }
    
    return (wins + ties * 0.5) / simulations;
}

} // namespace poker
