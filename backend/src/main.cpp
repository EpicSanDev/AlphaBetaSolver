#include <iostream>
#include <string>
#include <fstream>
#include <getopt.h>
#include <json/json.h>
#include "poker/cfr_solver.h"
#include "poker/game_tree.h"
#include "poker/evaluator.h"

using namespace poker;

void print_usage(const char* program_name) {
    std::cout << "Usage: " << program_name << " [OPTIONS]\n"
              << "Options:\n"
              << "  --task-type TYPE     Type de tâche: 'preflop' ou 'postflop'\n"
              << "  --params-file FILE   Fichier JSON avec les paramètres de simulation\n"
              << "  --output-format FMT  Format de sortie: 'json' ou 'text' (défaut: text)\n"
              << "  --help               Afficher cette aide\n"
              << "\nExemples:\n"
              << "  " << program_name << " --task-type preflop --params-file params.json --output-format json\n"
              << "  " << program_name << " (mode interactif)\n";
}

Json::Value load_params_file(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Impossible d'ouvrir le fichier de paramètres: " + filename);
    }
    
    Json::Value root;
    Json::CharReaderBuilder builder;
    std::string errors;
    
    if (!Json::parseFromStream(builder, file, &root, &errors)) {
        throw std::runtime_error("Erreur de parsing JSON: " + errors);
    }
    
    return root;
}

CFRConfig parse_solver_config(const Json::Value& config) {
    CFRConfig cfr_config;
    
    if (config.isMember("max_iterations")) {
        cfr_config.max_iterations = config["max_iterations"].asInt();
    }
    if (config.isMember("target_exploitability")) {
        cfr_config.target_exploitability = config["target_exploitability"].asDouble();
    }
    if (config.isMember("use_chance_sampling")) {
        cfr_config.use_chance_sampling = config["use_chance_sampling"].asBool();
    }
    if (config.isMember("use_discounting")) {
        cfr_config.use_discounting = config["use_discounting"].asBool();
    }
    if (config.isMember("alpha")) {
        cfr_config.alpha = config["alpha"].asDouble();
    }
    if (config.isMember("beta")) {
        cfr_config.beta = config["beta"].asDouble();
    }
    if (config.isMember("checkpoint_frequency")) {
        cfr_config.checkpoint_frequency = config["checkpoint_frequency"].asInt();
    }
    
    return cfr_config;
}

GameState parse_game_config(const Json::Value& config) {
    GameState state;
    
    // Configuration par défaut
    state.num_players = 2;
    state.street = 0; // preflop
    state.current_player = 0;
    state.button_position = 1;
    state.small_blind = 0.5;
    state.big_blind = 1.0;
    state.pot = 1.5; // SB + BB
    
    // Parser les paramètres depuis le JSON
    if (config.isMember("num_players")) {
        state.num_players = config["num_players"].asInt();
    }
    if (config.isMember("small_blind")) {
        state.small_blind = config["small_blind"].asDouble();
    }
    if (config.isMember("big_blind")) {
        state.big_blind = config["big_blind"].asDouble();
    }
    if (config.isMember("stack_size")) {
        double stack_size = config["stack_size"].asDouble();
        state.stacks.resize(state.num_players, stack_size);
    } else {
        state.stacks.resize(state.num_players, 100.0); // 100 BB par défaut
    }
    
    // Initialiser les mises (SB et BB déjà misés)
    state.bets.resize(state.num_players, 0.0);
    if (state.num_players >= 2) {
        state.bets[0] = state.small_blind;  // Small blind
        state.bets[1] = state.big_blind;    // Big blind
        state.stacks[0] -= state.small_blind;
        state.stacks[1] -= state.big_blind;
    }
    
    // Tailles de mise autorisées (en % du pot)
    state.allowed_bet_sizes = {0.33, 0.5, 0.75, 1.0}; // 33%, 50%, 75%, 100% pot
    if (config.isMember("allowed_bet_sizes")) {
        state.allowed_bet_sizes.clear();
        for (const auto& size : config["allowed_bet_sizes"]) {
            state.allowed_bet_sizes.push_back(size.asDouble());
        }
    }
    
    return state;
}

int run_simulation(const std::string& task_type, const Json::Value& params, const std::string& output_format) {
    try {
        // Parser la configuration
        CFRConfig solver_config = parse_solver_config(params["solver_config"]);
        GameState initial_state = parse_game_config(params["game_config"]);
        
        // Créer l'abstraction
        auto abstraction = std::make_shared<BasicAbstraction>();
        
        // Créer le solveur approprié
        std::unique_ptr<CFRSolver> solver;
        if (task_type == "preflop") {
            solver = std::make_unique<VanillaCFR>(abstraction, solver_config);
        } else if (task_type == "postflop") {
            // Pour le postflop, utiliser MCCFR si disponible
            solver = std::make_unique<VanillaCFR>(abstraction, solver_config);
        } else {
            throw std::runtime_error("Type de tâche non supporté: " + task_type);
        }
        
        // Exécuter la simulation
        std::cout << "Démarrage de la simulation " << task_type << "..." << std::endl;
        auto result = solver->solve(initial_state);
        
        // Obtenir la stratégie finale
        auto strategy = solver->get_strategy(initial_state, 0);
        
        // Formater la sortie
        if (output_format == "json") {
            Json::Value output;
            output["success"] = true;
            output["task_type"] = task_type;
            output["result"] = Json::Value();
            output["result"]["iterations_completed"] = result.iterations_completed;
            output["result"]["final_exploitability"] = result.final_exploitability;
            output["result"]["convergence_time"] = result.convergence_time_seconds;
            output["result"]["converged"] = result.converged;
            output["result"]["status"] = result.status_message;
            
            // Ajouter la stratégie
            Json::Value strategy_json(Json::arrayValue);
            for (size_t i = 0; i < strategy.size(); ++i) {
                strategy_json.append(strategy[i]);
            }
            output["result"]["strategy"]["player_0"] = strategy_json;
            
            // Ajouter les métadonnées
            output["result"]["metadata"]["solver_config"] = params["solver_config"];
            output["result"]["metadata"]["game_config"] = params["game_config"];
            
            Json::StreamWriterBuilder builder;
            std::unique_ptr<Json::StreamWriter> writer(builder.newStreamWriter());
            writer->write(output, &std::cout);
            std::cout << std::endl;
        } else {
            // Format texte
            std::cout << "\n=== Résultats de la simulation ===\n";
            std::cout << "Type: " << task_type << "\n";
            std::cout << "Statut: " << (result.converged ? "Convergé" : "Non convergé") << "\n";
            std::cout << "Itérations: " << result.iterations_completed << "\n";
            std::cout << "Exploitabilité finale: " << result.final_exploitability << "\n";
            std::cout << "Temps de convergence: " << result.convergence_time_seconds << "s\n";
            std::cout << "Message: " << result.status_message << "\n";
            
            std::cout << "\nStratégie du joueur 0:\n";
            for (size_t i = 0; i < strategy.size(); ++i) {
                std::cout << "Action " << i << ": " << strategy[i] << "\n";
            }
        }
        
        return 0;
        
    } catch (const std::exception& e) {
        if (output_format == "json") {
            Json::Value error_output;
            error_output["success"] = false;
            error_output["error"] = e.what();
            
            Json::StreamWriterBuilder builder;
            std::unique_ptr<Json::StreamWriter> writer(builder.newStreamWriter());
            writer->write(error_output, &std::cout);
            std::cout << std::endl;
        } else {
            std::cerr << "Erreur: " << e.what() << std::endl;
        }
        return 1;
    }
}

int interactive_mode() {
    std::cout << "=== Mode Interactif du Solveur GTO ===" << std::endl;
    std::cout << "Bonjour depuis le PokerSolverBackend !" << std::endl;
    
    // Exemple simple d'évaluation de main
    try {
        std::cout << "\nTest de l'évaluateur de mains:" << std::endl;
        
        // Créer quelques cartes de test
        Card ace_spades(Rank::ACE, Suit::SPADES);
        Card king_spades(Rank::KING, Suit::SPADES);
        Card queen_spades(Rank::QUEEN, Suit::SPADES);
        Card jack_spades(Rank::JACK, Suit::SPADES);
        Card ten_spades(Rank::TEN, Suit::SPADES);
        
        std::vector<Card> royal_flush = {ace_spades, king_spades, queen_spades, jack_spades, ten_spades};
        
        auto strength = HandEvaluator::evaluate_five_cards(royal_flush);
        std::cout << "Main: " << board_to_string(royal_flush) << std::endl;
        std::cout << "Force: " << strength.to_string() << std::endl;
        
        // Test d'équité simple
        Hand hero = {ace_spades, king_spades};
        Hand villain = {Card(Rank::TWO, Suit::CLUBS), Card(Rank::SEVEN, Suit::DIAMONDS)};
        std::vector<Hand> villain_range = {villain};
        Board board;
        
        double equity = HandEvaluator::monte_carlo_equity(hero, villain_range, board, 1000);
        std::cout << "\nÉquité de " << hand_to_string(hero) << " vs " << hand_to_string(villain) << ": " 
                  << (equity * 100) << "%" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "Erreur lors du test: " << e.what() << std::endl;
    }
    
    return 0;
}

int main(int argc, char* argv[]) {
    std::string task_type;
    std::string params_file;
    std::string output_format = "text";
    
    // Options de ligne de commande
    struct option long_options[] = {
        {"task-type", required_argument, 0, 't'},
        {"params-file", required_argument, 0, 'p'},
        {"output-format", required_argument, 0, 'o'},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0}
    };
    
    int option_index = 0;
    int c;
    
    while ((c = getopt_long(argc, argv, "t:p:o:h", long_options, &option_index)) != -1) {
        switch (c) {
            case 't':
                task_type = optarg;
                break;
            case 'p':
                params_file = optarg;
                break;
            case 'o':
                output_format = optarg;
                break;
            case 'h':
                print_usage(argv[0]);
                return 0;
            case '?':
                print_usage(argv[0]);
                return 1;
            default:
                break;
        }
    }
    
    // Si les paramètres de ligne de commande sont fournis, mode CLI
    if (!task_type.empty() && !params_file.empty()) {
        try {
            Json::Value params = load_params_file(params_file);
            return run_simulation(task_type, params, output_format);
        } catch (const std::exception& e) {
            std::cerr << "Erreur: " << e.what() << std::endl;
            return 1;
        }
    }
    
    // Sinon, mode interactif
    return interactive_mode();
}