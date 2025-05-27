#pragma once

#include <string>
#include <vector>
#include <cstdint>
#include <functional> // Pour std::hash

namespace poker {

enum class Suit : uint8_t {
    CLUBS = 0,
    DIAMONDS = 1,
    HEARTS = 2,
    SPADES = 3
};

enum class Rank : uint8_t {
    TWO = 2, THREE, FOUR, FIVE, SIX, SEVEN, EIGHT, NINE, TEN,
    JACK, QUEEN, KING, ACE
};

class Card {
public:
    // Default constructor to support std::pair and container initialization
    Card() : rank_(Rank::TWO), suit_(Suit::CLUBS) {}
    Card(Rank rank, Suit suit);
    Card(const std::string& str); // "As", "Kh", etc.
    
    Rank rank() const { return rank_; }
    Suit suit() const { return suit_; }
    uint8_t index() const { return static_cast<uint8_t>(rank_) * 4 + static_cast<uint8_t>(suit_); }
    
    std::string to_string() const;
    bool operator==(const Card& other) const;
    bool operator<(const Card& other) const;
    
private:
    Rank rank_;
    Suit suit_;
};

using Hand = std::pair<Card, Card>;
using Board = std::vector<Card>;

// Utilitaires pour les cartes
std::vector<Card> all_cards();
std::string hand_to_string(const Hand& hand);
std::string board_to_string(const Board& board);

} // namespace poker

// Spécialisation de std::hash pour poker::Card
// Doit être dans le namespace std
namespace std {
    template <>
    struct hash<poker::Card> {
        std::size_t operator()(const poker::Card& card) const {
            // Utiliser l'index unique de la carte pour le hachage
            return std::hash<uint8_t>()(card.index());
        }
    };
}
