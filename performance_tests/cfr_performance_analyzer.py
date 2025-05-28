#!/usr/bin/env python3
"""
Performance analyzer for CFR algorithms in AlphaBetaSolver
Tests convergence speed, memory usage, and scalability
"""

import os
import sys
import time
import json
import subprocess
import psutil
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
from pathlib import Path

@dataclass
class PerformanceMetrics:
    """Métriques de performance pour les algorithmes CFR"""
    iterations: int
    exploitability: float
    time_seconds: float
    memory_mb: float
    convergence_rate: float
    cpu_usage: float

class CFRPerformanceAnalyzer:
    """Analyseur de performance pour les algorithmes CFR"""
    
    def __init__(self, poker_solver_path: str):
        self.poker_solver_path = poker_solver_path
        self.results_dir = Path(__file__).parent / "results"
        self.results_dir.mkdir(exist_ok=True)
        
    def benchmark_solver(self, solver_type: str, config: Dict[str, Any], 
                        game_config: Dict[str, Any], iterations_list: List[int]) -> List[PerformanceMetrics]:
        """Benchmark un solveur CFR avec différents nombres d'itérations"""
        
        results = []
        
        for max_iterations in iterations_list:
            print(f"Testing {solver_type} with {max_iterations} iterations...")
            
            # Configuration pour ce test
            test_config = config.copy()
            test_config["max_iterations"] = max_iterations
            
            # Créer le fichier de configuration temporaire
            test_data = {
                "task_type": "preflop",
                "params": {
                    "solver_config": test_config,
                    "game_config": game_config
                }
            }
            
            config_file = self.results_dir / f"test_config_{solver_type}_{max_iterations}.json"
            with open(config_file, 'w') as f:
                json.dump(test_data, f, indent=2)
            
            # Mesurer les performances
            metrics = self._run_performance_test(config_file)
            if metrics:
                results.append(metrics)
            
            # Nettoyer
            config_file.unlink(missing_ok=True)
            
        return results
    
    def _run_performance_test(self, config_file: Path) -> PerformanceMetrics:
        """Exécute un test de performance et collecte les métriques"""
        
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        try:
            # Exécuter le solveur avec monitoring
            process = psutil.Popen([
                self.poker_solver_path, 
                "simulation", 
                str(config_file), 
                "json"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Monitorer l'utilisation CPU et mémoire
            cpu_samples = []
            memory_samples = []
            
            while process.is_running():
                try:
                    cpu_percent = process.cpu_percent()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    
                    cpu_samples.append(cpu_percent)
                    memory_samples.append(memory_mb)
                    
                    time.sleep(0.1)  # Sample every 100ms
                except psutil.NoSuchProcess:
                    break
            
            stdout, stderr = process.communicate()
            end_time = time.time()
            
            if process.returncode != 0:
                print(f"Error running solver: {stderr}")
                return None
            
            # Parser les résultats
            try:
                result = json.loads(stdout)
                
                metrics = PerformanceMetrics(
                    iterations=result.get("iterations_completed", 0),
                    exploitability=result.get("final_exploitability", 1.0),
                    time_seconds=end_time - start_time,
                    memory_mb=max(memory_samples) if memory_samples else start_memory,
                    convergence_rate=self._calculate_convergence_rate(result),
                    cpu_usage=np.mean(cpu_samples) if cpu_samples else 0.0
                )
                
                return metrics
                
            except json.JSONDecodeError as e:
                print(f"Error parsing solver output: {e}")
                print(f"Stdout: {stdout}")
                return None
            
        except Exception as e:
            print(f"Error running performance test: {e}")
            return None
    
    def _calculate_convergence_rate(self, result: Dict[str, Any]) -> float:
        """Calcule le taux de convergence basé sur l'exploitabilité finale"""
        final_exploitability = result.get("final_exploitability", 1.0)
        target_exploitability = 0.005  # 0.5% du pot
        
        if final_exploitability <= target_exploitability:
            return 1.0  # Converged
        else:
            # Calculate how close we got (0.0 to 1.0)
            return max(0.0, 1.0 - (final_exploitability - target_exploitability) / target_exploitability)
    
    def compare_algorithms(self) -> Dict[str, Any]:
        """Compare les performances des différents algorithmes CFR"""
        
        # Configuration de base
        base_solver_config = {
            "target_exploitability": 0.005,
            "use_chance_sampling": False,
            "use_discounting": True,
            "alpha": 1.5,
            "beta": 0.0,
            "checkpoint_frequency": 0
        }
        
        game_config = {
            "num_players": 2,
            "initial_stack": 1000,
            "small_blind": 5,
            "big_blind": 10,
            "ante": 0
        }
        
        # Tests avec différents nombres d'itérations
        iterations_list = [100, 250, 500, 1000, 2000]
        
        results = {}
        
        # Test VanillaCFR
        print("Testing VanillaCFR...")
        vanilla_config = base_solver_config.copy()
        vanilla_config["use_chance_sampling"] = False
        results["VanillaCFR"] = self.benchmark_solver("vanilla", vanilla_config, game_config, iterations_list)
        
        # Test ChanceSamplingCFR (MCCFR)
        print("Testing ChanceSamplingCFR...")
        mccfr_config = base_solver_config.copy()
        mccfr_config["use_chance_sampling"] = True
        results["ChanceSamplingCFR"] = self.benchmark_solver("mccfr", mccfr_config, game_config, iterations_list)
        
        # Test CFR+
        print("Testing CFR+...")
        cfrplus_config = base_solver_config.copy()
        cfrplus_config["use_chance_sampling"] = False
        results["CFRPlus"] = self.benchmark_solver("cfrplus", cfrplus_config, game_config, iterations_list)
        
        return results
    
    def generate_performance_report(self, results: Dict[str, List[PerformanceMetrics]]) -> None:
        """Génère un rapport de performance complet avec visualisations"""
        
        # Créer les graphiques
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # Graphique 1: Convergence vs Itérations
        for algo_name, metrics_list in results.items():
            if metrics_list:
                iterations = [m.iterations for m in metrics_list]
                exploitabilities = [m.exploitability for m in metrics_list]
                ax1.plot(iterations, exploitabilities, 'o-', label=algo_name, linewidth=2)
        
        ax1.set_xlabel('Iterations')
        ax1.set_ylabel('Final Exploitability')
        ax1.set_title('Convergence Performance')
        ax1.set_yscale('log')
        ax1.grid(True, alpha=0.3)
        ax1.legend()
        ax1.axhline(y=0.005, color='r', linestyle='--', alpha=0.7, label='Target (0.5%)')
        
        # Graphique 2: Temps d'exécution vs Itérations
        for algo_name, metrics_list in results.items():
            if metrics_list:
                iterations = [m.iterations for m in metrics_list]
                times = [m.time_seconds for m in metrics_list]
                ax2.plot(iterations, times, 'o-', label=algo_name, linewidth=2)
        
        ax2.set_xlabel('Iterations')
        ax2.set_ylabel('Execution Time (seconds)')
        ax2.set_title('Runtime Performance')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # Graphique 3: Utilisation mémoire vs Itérations
        for algo_name, metrics_list in results.items():
            if metrics_list:
                iterations = [m.iterations for m in metrics_list]
                memory = [m.memory_mb for m in metrics_list]
                ax3.plot(iterations, memory, 'o-', label=algo_name, linewidth=2)
        
        ax3.set_xlabel('Iterations')
        ax3.set_ylabel('Memory Usage (MB)')
        ax3.set_title('Memory Performance')
        ax3.grid(True, alpha=0.3)
        ax3.legend()
        
        # Graphique 4: Efficacité (Convergence/Temps)
        for algo_name, metrics_list in results.items():
            if metrics_list:
                iterations = [m.iterations for m in metrics_list]
                efficiency = [m.convergence_rate / max(m.time_seconds, 0.1) for m in metrics_list]
                ax4.plot(iterations, efficiency, 'o-', label=algo_name, linewidth=2)
        
        ax4.set_xlabel('Iterations')
        ax4.set_ylabel('Efficiency (Convergence Rate / Time)')
        ax4.set_title('Algorithm Efficiency')
        ax4.grid(True, alpha=0.3)
        ax4.legend()
        
        plt.tight_layout()
        plt.savefig(self.results_dir / 'cfr_performance_comparison.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        # Générer rapport texte
        self._generate_text_report(results)
    
    def _generate_text_report(self, results: Dict[str, List[PerformanceMetrics]]) -> None:
        """Génère un rapport texte détaillé"""
        
        report_path = self.results_dir / 'performance_report.md'
        
        with open(report_path, 'w') as f:
            f.write("# CFR Performance Analysis Report\n\n")
            f.write(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Algorithm Comparison Summary\n\n")
            
            for algo_name, metrics_list in results.items():
                if not metrics_list:
                    continue
                    
                f.write(f"### {algo_name}\n\n")
                
                # Calculer les statistiques
                avg_convergence = np.mean([m.convergence_rate for m in metrics_list])
                avg_time_per_1k_iter = np.mean([m.time_seconds / (m.iterations / 1000) for m in metrics_list if m.iterations > 0])
                avg_memory = np.mean([m.memory_mb for m in metrics_list])
                best_exploitability = min([m.exploitability for m in metrics_list])
                
                f.write(f"- **Average Convergence Rate**: {avg_convergence:.3f}\n")
                f.write(f"- **Average Time per 1K iterations**: {avg_time_per_1k_iter:.2f}s\n")
                f.write(f"- **Average Memory Usage**: {avg_memory:.1f} MB\n")
                f.write(f"- **Best Exploitability Achieved**: {best_exploitability:.6f}\n")
                f.write(f"- **Target Achievement**: {'✅ Yes' if best_exploitability <= 0.005 else '❌ No'}\n\n")
                
                # Table détaillée
                f.write("| Iterations | Exploitability | Time (s) | Memory (MB) | CPU (%) | Convergence Rate |\n")
                f.write("|------------|----------------|----------|-------------|---------|------------------|\n")
                
                for m in metrics_list:
                    f.write(f"| {m.iterations} | {m.exploitability:.6f} | {m.time_seconds:.2f} | {m.memory_mb:.1f} | {m.cpu_usage:.1f} | {m.convergence_rate:.3f} |\n")
                
                f.write("\n")
            
            # Recommandations
            f.write("## Recommendations\n\n")
            
            # Trouver le meilleur algorithme
            best_algo = None
            best_score = 0
            
            for algo_name, metrics_list in results.items():
                if metrics_list:
                    # Score basé sur convergence et efficacité
                    avg_convergence = np.mean([m.convergence_rate for m in metrics_list])
                    avg_efficiency = np.mean([m.convergence_rate / max(m.time_seconds, 0.1) for m in metrics_list])
                    score = avg_convergence * 0.7 + avg_efficiency * 0.3
                    
                    if score > best_score:
                        best_score = score
                        best_algo = algo_name
            
            if best_algo:
                f.write(f"### Recommended Algorithm: **{best_algo}**\n\n")
                f.write(f"Based on the performance analysis, {best_algo} shows the best overall performance ")
                f.write(f"considering convergence rate and computational efficiency.\n\n")
            
            # Recommandations spécifiques
            f.write("### Specific Recommendations:\n\n")
            f.write("1. **For Fast Convergence**: Use CFR+ for its superior regret matching\n")
            f.write("2. **For Large Games**: Consider ChanceSamplingCFR to reduce memory usage\n")
            f.write("3. **For Production**: Implement parallel processing for faster convergence\n")
            f.write("4. **Optimization**: Consider implementing abstraction improvements\n\n")
            
        print(f"Performance report generated: {report_path}")

def main():
    """Point d'entrée principal"""
    
    # Chemin vers l'exécutable PokerSolver
    poker_solver_path = "/Users/bastienjavaux/Desktop/AlphaBetaSolver/backend/build/src/PokerSolver"
    
    if not os.path.exists(poker_solver_path):
        print(f"Error: PokerSolver not found at {poker_solver_path}")
        print("Please compile the C++ backend first:")
        print("cd /Users/bastienjavaux/Desktop/AlphaBetaSolver/backend && mkdir -p build && cd build && cmake .. && make")
        return 1
    
    # Créer l'analyseur
    analyzer = CFRPerformanceAnalyzer(poker_solver_path)
    
    print("Starting CFR Performance Analysis...")
    print("This may take several minutes...")
    
    # Exécuter les tests de comparaison
    results = analyzer.compare_algorithms()
    
    # Générer le rapport
    print("\nGenerating performance report...")
    analyzer.generate_performance_report(results)
    
    print("\nPerformance analysis completed!")
    print(f"Results saved in: {analyzer.results_dir}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
