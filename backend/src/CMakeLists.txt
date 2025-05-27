# Sources du projet
set(POKER_SOURCES
    main.cpp
    poker/card.cpp
    poker/evaluator.cpp
    poker/game_tree.cpp
    poker/cfr_solver.cpp
)

# Ajout de l'exécutable principal
add_executable(PokerSolver ${POKER_SOURCES})

# Configuration des includes
target_include_directories(PokerSolver PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${JSONCPP_INCLUDE_DIRS}
)

# Liaison des bibliothèques
target_link_libraries(PokerSolver PRIVATE 
    ${JSONCPP_LIBRARIES}
)

# Définir les flags de compilation pour jsoncpp si nécessaire
if(JSONCPP_CFLAGS_OTHER)
    target_compile_options(PokerSolver PRIVATE ${JSONCPP_CFLAGS_OTHER})
endif()