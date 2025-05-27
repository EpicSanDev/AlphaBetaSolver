#include "card.h"
#include <stdexcept>
#include <sstream>

namespace poker {

Card::Card(Rank rank, Suit suit) : rank_(rank), suit_(suit) {}

Card::Card(const std::string& str) {
    if (str.length() != 2) {
        throw std::invalid_argument("Invalid card string: " + str);
    }
    
    // Parse rank
    char rank_char = str[0];
    switch (rank_char) {
        case '2': rank_ = Rank::TWO; break;
        case '3': rank_ = Rank::THREE; break;
        case '4': rank_ = Rank::FOUR; break;
        case '5': rank_ = Rank::FIVE; break;
        case '6': rank_ = Rank::SIX; break;
        case '7': rank_ = Rank::SEVEN; break;
        case '8': rank_ = Rank::EIGHT; break;
        case '9': rank_ = Rank::NINE; break;
        case 'T': rank_ = Rank::TEN; break;
        case 'J': rank_ = Rank::JACK; break;
        case 'Q': rank_ = Rank::QUEEN; break;
        case 'K': rank_ = Rank::KING; break;
        case 'A': rank_ = Rank::ACE; break;
        default: throw std::invalid_argument("Invalid rank: " + std::string(1, rank_char));
    }
    
    // Parse suit
    char suit_char = str[1];
    switch (suit_char) {
        case 'c': case 'C': suit_ = Suit::CLUBS; break;
        case 'd': case 'D': suit_ = Suit::DIAMONDS; break;
        case 'h': case 'H': suit_ = Suit::HEARTS; break;
        case 's': case 'S': suit_ = Suit::SPADES; break;
        default: throw std::invalid_argument("Invalid suit: " + std::string(1, suit_char));
    }
}

std::string Card::to_string() const {
    std::string result;
    
    // Rank
    switch (rank_) {
        case Rank::TWO: result += '2'; break;
        case Rank::THREE: result += '3'; break;
        case Rank::FOUR: result += '4'; break;
        case Rank::FIVE: result += '5'; break;
        case Rank::SIX: result += '6'; break;
        case Rank::SEVEN: result += '7'; break;
        case Rank::EIGHT: result += '8'; break;
        case Rank::NINE: result += '9'; break;
        case Rank::TEN: result += 'T'; break;
        case Rank::JACK: result += 'J'; break;
        case Rank::QUEEN: result += 'Q'; break;
        case Rank::KING: result += 'K'; break;
        case Rank::ACE: result += 'A'; break;
    }
    
    // Suit
    switch (suit_) {
        case Suit::CLUBS: result += 'c'; break;
        case Suit::DIAMONDS: result += 'd'; break;
        case Suit::HEARTS: result += 'h'; break;
        case Suit::SPADES: result += 's'; break;
    }
    
    return result;
}

bool Card::operator==(const Card& other) const {
    return rank_ == other.rank_ && suit_ == other.suit_;
}

bool Card::operator<(const Card& other) const {
    if (rank_ != other.rank_) return rank_ < other.rank_;
    return suit_ < other.suit_;
}

std::vector<Card> all_cards() {
    std::vector<Card> cards;
    cards.reserve(52);
    
    for (int rank = static_cast<int>(Rank::TWO); rank <= static_cast<int>(Rank::ACE); ++rank) {
        for (int suit = 0; suit <= 3; ++suit) {
            cards.emplace_back(static_cast<Rank>(rank), static_cast<Suit>(suit));
        }
    }
    
    return cards;
}

std::string hand_to_string(const Hand& hand) {
    return hand.first.to_string() + hand.second.to_string();
}

std::string board_to_string(const Board& board) {
    std::ostringstream oss;
    for (size_t i = 0; i < board.size(); ++i) {
        if (i > 0) oss << " ";
        oss << board[i].to_string();
    }
    return oss.str();
}

} // namespace poker
