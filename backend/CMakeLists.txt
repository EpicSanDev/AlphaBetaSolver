cmake_minimum_required(VERSION 3.10)

# Nom du projet
project(PokerSolverBackend LANGUAGES CXX)

# Standard C++
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Options de compilation
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g -O0 -Wall -Wextra")
else()
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -DNDEBUG")
endif()

# Trouver les dépendances
find_package(PkgConfig REQUIRED)
pkg_check_modules(JSONCPP jsoncpp)

# Si jsoncpp n'est pas trouvé via pkg-config, essayer find_package
if(NOT JSONCPP_FOUND)
    find_package(jsoncpp REQUIRED)
    set(JSONCPP_LIBRARIES jsoncpp)
endif()

# Pour macOS avec Homebrew
if(APPLE)
    include_directories(${JSONCPP_INCLUDE_DIRS})
    link_directories(${JSONCPP_LIBRARY_DIRS})
    # Fallback to Homebrew location if still not found
    if(NOT JSONCPP_FOUND)
        include_directories(/opt/homebrew/include)
        link_directories(/opt/homebrew/lib)
        set(JSONCPP_LIBRARIES jsoncpp)
    endif()
endif()

# Ajout du sous-répertoire src pour les sources
add_subdirectory(src)