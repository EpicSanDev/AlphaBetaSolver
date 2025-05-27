# Proposition d'Architecture pour le Solveur de Poker GTO

## 1. Choix des Langages de Programmation et Technologies Principales

*   **Backend (Calculs Intensifs - Modules de Simulation Préflop/Postflop) :**
    *   **Langage :** C++ (moderne, par exemple C++17 ou C++20)
    *   **Justification :** Performance cruciale pour les milliards de simulations préflop et les calculs complexes postflop. C++ offre un contrôle fin de la mémoire et une optimisation poussée. La structure de base du projet backend C++ a d'ailleurs déjà été initialisée.
    *   **Compilation :** CMake pour la gestion de la compilation multiplateforme.
    *   **Bibliothèques C++ notables :**
        *   Boost (pour divers utilitaires, structures de données avancées si besoin).
        *   Eigen ou Armadillo (pour les calculs matriciels si l'algorithme GTO en bénéficie directement).
        *   Une bibliothèque de logging performante (par exemple, spdlog).

*   **Backend (Gestion, API, Orchestration - Nœud Maître, Nœuds de Calcul Agents) :**
    *   **Langage :** Python 3.8+
    *   **Justification :** Développement rapide, vaste écosystème de bibliothèques, excellent pour la gestion des tâches, les API REST, et l'intégration avec d'autres services. Le document PDF suggère fortement Python pour le nœud maître et les agents des nœuds de calcul (`master_node.py`, `compute_node.py`).
    *   **Framework API :** FastAPI ou Flask/Django. FastAPI est moderne, performant et intègre la validation de données avec Pydantic et la documentation OpenAPI automatique (Swagger UI), ce qui correspond bien à la documentation API mentionnée dans le PDF (ligne 993).
    *   **Communication C++/Python :**
        *   `pybind11` pour créer des bindings Python pour les modules de calcul C++. Cela permet d'appeler les cœurs C++ performants depuis la logique Python.
        *   Alternativement, communication inter-processus (IPC) via des sockets ou des pipes si les modules C++ sont des exécutables séparés.

*   **Frontend (Interface Utilisateur) :**
    *   **Type :** Application Web (Single Page Application - SPA)
    *   **Justification :** Accessibilité multiplateforme (navigateur web), déploiement centralisé, facilité de mise à jour. L'interface d'administration est déjà envisagée comme une application web.
    *   **Langage/Framework :**
        *   JavaScript/TypeScript.
        *   React, Vue.js, ou Angular. React et Vue.js sont populaires pour leur flexibilité et leur performance. Le choix peut dépendre des compétences de l'équipe.
    *   **Bibliothèques de visualisation :** D3.js, Chart.js, ou des bibliothèques de composants UI spécifiques au framework (ex: Material-UI pour React, Vuetify pour Vue) pour afficher les ranges, les arbres de décision, et les graphiques d'EV.

## 2. Architecture pour l'Exécution Distribuée en Mode Cluster

*   **Technologie Envisagée :** Architecture basée sur des Microservices avec une file de messages.
    *   **Nœud Maître :** Orchestre les tâches, gère la file de messages, expose l'API REST pour l'UI et la soumission de jobs.
    *   **Nœuds de Calcul :** Exécutent les "agents de calcul" (en Python) qui consomment les tâches de la file. Ces agents invoquent les modules de simulation C++ pour les calculs intensifs.
    *   **File de Messages (Message Broker) :** RabbitMQ (mentionné dans le PDF comme option) ou Redis Streams.
        *   **Justification :** Découplage fort entre le producteur de tâches (Nœud Maître) et les consommateurs (Nœuds de Calcul). Permet la scalabilité, la résilience (persistance des messages), et la distribution asynchrone des tâches. RabbitMQ est robuste pour des files de tâches complexes.
    *   **Communication Inter-services :** REST APIs pour la communication synchrone (UI vers Maître), et la file de messages pour la communication asynchrone (Maître vers Nœuds de Calcul). gRPC pourrait être envisagé pour la communication interne à haute performance entre les services Python et les agents si nécessaire, ou entre les agents et les modules C++ s'ils sont des services distincts.

*   **Mécanisme de Distribution, Parallélisation, Synchronisation/Agrégation :**
    *   **Distribution :**
        1.  L'UI soumet une simulation (préflop ou postflop) via l'API REST au Nœud Maître.
        2.  Le Nœud Maître décompose la simulation en sous-tâches plus petites (par exemple, un batch de mains à simuler, une partie d'un arbre de jeu à explorer).
        3.  Ces sous-tâches sont publiées comme messages dans la file RabbitMQ.
    *   **Parallélisation :**
        *   Plusieurs Nœuds de Calcul (et potentiellement plusieurs workers par nœud) consomment les tâches de la file en parallèle.
        *   Chaque tâche est traitée par un module de simulation C++.
    *   **Synchronisation/Agrégation :**
        1.  Les Nœuds de Calcul envoient les résultats partiels (par exemple, EV, fréquences d'action pour un sous-ensemble de mains) à un service d'agrégation sur le Nœud Maître ou directement à une base de données optimisée pour les écritures fréquentes (voir section Persistance).
        2.  Le Nœud Maître (ou un service dédié) agrège ces résultats partiels pour former la solution complète. Pour les algorithmes itératifs comme CFR, les mises à jour de stratégie/regret peuvent être agrégées à chaque itération.
        3.  L'état de la simulation (par exemple, nombre d'itérations, convergence) est stocké et mis à jour.

*   **Déploiement :** Docker pour encapsuler chaque service (Maître, Nœud de Calcul, RabbitMQ, Base de Données, Frontend). Kubernetes ou Docker Swarm pour l'orchestration des conteneurs en cluster, facilitant le scaling et la gestion (comme suggéré par l'exemple Terraform pour AWS dans le PDF).

## 3. Algorithme de Résolution GTO

*   **Algorithme :** **Discounted CFR (DCFR)** ou **CFR+**.
    *   **Justification :**
        *   **CFR+ :** Converge plus rapidement que le CFR vanille en pratique, ce qui est crucial pour des arbres de jeu volumineux. Il garantit également une convergence vers un équilibre de Nash.
        *   **DCFR :** Peut offrir une convergence encore plus rapide dans les premières itérations et est souvent plus simple à implémenter correctement que certaines variantes de CFR+. Il pondère davantage les itérations récentes, ce qui peut être bénéfique.
        *   Le choix final pourrait dépendre d'une phase de prototypage et de tests de performance sur des jeux réduits.
    *   **MCCFR (Monte Carlo CFR) :** Particulièrement adapté pour les jeux très volumineux où l'exploration de l'arbre entier est infaisable à chaque itération. Il utilise l'échantillonnage. Pour le postflop, où l'arbre est immense, MCCFR (en particulier des variantes comme Public Chance Sampling MCCFR) est un candidat très sérieux.
    *   **Proposition :** Commencer avec CFR+ pour le préflop (où les arbres peuvent être gérables avec une bonne abstraction) et explorer MCCFR pour le postflop.

*   **Objectif de Précision :** L'exploitabilité (< 0.5% EV du pot ou < 5 bb/100) sera la métrique clé pour arrêter les simulations. Cela nécessite de calculer périodiquement la "best response" à la stratégie actuelle.

## 4. Techniques d'Abstraction du Jeu (pour le module postflop)

*   **Abstraction de Cartes (Card Abstraction) :**
    *   **Bucketing par Similarité de Main :**
        1.  **Pré-flop :** Les mains sont déjà naturellement bucketées (AA, AKs, etc.).
        2.  **Post-flop :** Regrouper les mains qui ont une force et/ou un potentiel similaires sur un board donné.
            *   **Abstraction basée sur l'équité :** Calculer l'équité de chaque main contre une range de mains adverses représentative. Les mains avec des équités similaires sont regroupées.
            *   **Abstraction basée sur le potentiel :** (par exemple, OCHS - Opponent Hand Clustering System, ou EHS - Expected Hand Strength). Regrouper les mains en fonction de leur force actuelle et de leur potentiel d'amélioration (par exemple, tirages couleur, tirages quinte, potentiel de faire une meilleure paire).
            *   **Clustering :** Utiliser des algorithmes de k-means ou d'autres techniques de clustering sur des vecteurs de caractéristiques des mains (équité, potentiel, etc.) pour créer des buckets.
    *   **Isomorphisme des Flops :** Regrouper les flops structurellement identiques (par exemple, As Ks Qs est stratégiquement similaire à Ad Kd Qd). Cela réduit considérablement le nombre de flops uniques à analyser.

*   **Abstraction d'Actions (Action Abstraction) :**
    *   **Discrétisation des Tailles de Mise :** Limiter le nombre de tailles de mise autorisées (par exemple, 33% pot, 50% pot, 75% pot, 100% pot, all-in) comme spécifié dans le PDF. Le choix de ces tailles doit être stratégiquement pertinent.
    *   **Limitation du Nombre de Raises :** Par exemple, autoriser un seul raise ou un nombre limité de re-raises par street.
    *   **Élagage de l'Arbre de Jeu :** Potentiellement ignorer certaines branches de l'arbre de jeu qui sont rarement atteintes ou ont un impact EV faible, bien que cela doive être fait avec prudence pour ne pas biaiser la solution.

## 5. Interaction entre les Modules

```mermaid
graph TD
    UI[Interface Utilisateur (Web App)] -->|1. Config Simu / Visualisation| APIServer{API Server (Nœud Maître - Python/FastAPI)}
    APIServer -->|2. Décompose & Enqueue Tâches| MsgQueue[(RabbitMQ)]
    MsgQueue -->|3. Récupère Tâche| ComputeAgent[Agent de Calcul (Nœud de Calcul - Python)]
    ComputeAgent -->|4. Exécute Simu| SimCoreCPP[Cœur de Simulation (C++)]
    SimCoreCPP -->|5. Retourne Résultat Partiel| ComputeAgent
    ComputeAgent -->|6. Envoie Résultat Partiel| Aggregator[Service d'Agrégation / DB (Nœud Maître)]
    Aggregator -->|7. Stocke / Met à Jour| DB[(Base de Données)]
    DB -->|8. Fournit Données Aggrégées| APIServer

    subgraph Nœud Maître
        APIServer
        MsgQueue
        Aggregator
        DB
    end

    subgraph "Nœud(s) de Calcul"
        ComputeAgent
        SimCoreCPP
    end
```

*   **Flux Principal (simplifié) :**
    1.  **Utilisateur (via UI) :** Configure les paramètres de simulation (structure de tournoi, stacks, ranges, board, etc.) et soumet la tâche.
    2.  **API Server (Nœud Maître) :** Valide la requête, la décompose en sous-tâches gérables, et les publie dans la file de messages (RabbitMQ).
    3.  **Agent de Calcul (Nœud de Calcul) :** Récupère une tâche de la file.
    4.  **Agent de Calcul :** Invoque le module de simulation C++ approprié (préflop/ICM ou postflop/GTO) avec les paramètres de la tâche.
    5.  **Cœur de Simulation C++ :** Exécute les calculs (par exemple, une itération de CFR, une simulation de N mains).
    6.  **Agent de Calcul :** Récupère le résultat partiel du module C++ et le transmet au service d'agrégation ou directement à la base de données.
    7.  **Service d'Agrégation (Nœud Maître) :** Collecte les résultats partiels, les agrège, met à jour la stratégie globale, et vérifie la convergence.
    8.  **API Server :** Permet à l'UI de requêter l'état d'avancement et les résultats finaux une fois la simulation terminée.

## 6. Persistance des Données

*   **Base de Données Relationnelle (par exemple, PostgreSQL - mentionné dans le PDF) :**
    *   **Usage :** Configurations des simulations, métadonnées des jobs, structure des tournois, ranges des joueurs, utilisateurs et permissions. Données structurées avec des relations claires.
    *   **Justification :** ACID, requêtes SQL puissantes, maturité.

*   **Base de Données NoSQL (par exemple, MongoDB - mentionné dans le PDF, ou une base de données orientée colonnes comme Cassandra/ScyllaDB pour les séries temporelles/résultats massifs) :**
    *   **Usage :**
        *   Stockage des résultats de simulation détaillés (par exemple, stratégies GTO pour des millions de nœuds d'arbre de jeu, EV, fréquences). Ces données peuvent être volumineuses et moins structurées.
        *   Potentiellement pour les regrets et les stratégies moyennes dans les algorithmes CFR, si leur volume devient très important.
    *   **Justification :** Scalabilité horizontale, flexibilité du schéma, performance pour les écritures/lectures de gros volumes de données. MongoDB est un bon choix généraliste NoSQL. Pour des données de type "séries de résultats" ou des tables de stratégies très larges, une base orientée colonnes pourrait être plus performante.

*   **Système de Fichiers Distribué (optionnel, pour les très gros artefacts) :**
    *   **Usage :** Pour stocker des "checkpoints" de simulations très longues ou des solutions complètes sérialisées si elles sont trop volumineuses pour les bases de données.
    *   **Exemples :** HDFS (si Spark est utilisé), GlusterFS, ou stockage objet cloud (S3, Google Cloud Storage).

*   **Checkpointing et Reprise :**
    *   Les simulations longues (surtout postflop) doivent implémenter un mécanisme de checkpointing robuste.
    *   L'état de la simulation (par exemple, les regrets cumulés dans CFR, le nombre d'itérations) sera sauvegardé périodiquement dans la base de données ou sur un système de fichiers.
    *   En cas de panne d'un nœud ou du système, la simulation pourra reprendre depuis le dernier checkpoint valide.