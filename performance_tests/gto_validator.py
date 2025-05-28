#!/usr/bin/env python3
"""
GTO Strategy Validator for AlphaBetaSolver
Validates the accuracy and correctness of computed strategies
"""

import json
import requests
import numpy as np
import time
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import matplotlib.pyplot as plt
from itertools import combinations

@dataclass
class ValidationResult:
    """Résultat de validation d'une stratégie"""
    test_name: str
    passed: bool
    score: float
    details: Dict[str, Any]
    error_message: Optional[str] = None

class GTOStrategyValidator:
    """Validateur de stratégies GTO pour AlphaBetaSolver"""
    
    def __init__(self, api_base_url: str = "http://localhost:8002"):
        self.api_base_url = api_base_url
        self.results_dir = Path(__file__).parent / "validation_results"
        self.results_dir.mkdir(exist_ok=True)
        
    def create_test_simulation(self, config: Dict[str, Any]) -> Optional[str]:
        """Crée une simulation de test et retourne son ID"""
        try:
            response = requests.post(
                f"{self.api_base_url}/api/v1/simulations",
                json=config,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()["simulation_id"]
            else:
                print(f"Failed to create simulation: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error creating simulation: {e}")
            return None
    
    def wait_for_completion(self, simulation_id: str, max_wait: int = 300) -> Dict[str, Any]:
        """Attend qu'une simulation se termine et retourne les résultats"""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(
                    f"{self.api_base_url}/api/v1/simulations/{simulation_id}",
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if data["status"] in ["completed", "failed", "error"]:
                        return data
                time.sleep(2)
            except Exception as e:
                print(f"Error checking simulation status: {e}")
                time.sleep(5)
        
        return {"status": "timeout", "error": "Simulation timed out"}
    
    def validate_nash_equilibrium_properties(self) -> ValidationResult:
        """Valide les propriétés d'équilibre de Nash"""
        
        config = {
            "name": "nash_equilibrium_test",
            "description": "Test des propriétés d'équilibre de Nash",
            "solver_type": "cfr_plus",
            "game_config": {
                "num_players": 2,
                "initial_stack": 1000,
                "small_blind": 5,
                "big_blind": 10,
                "ante": 0
            },
            "solver_config": {
                "max_iterations": 1000,
                "target_exploitability": 0.001,  # Très strict pour la validation
                "use_chance_sampling": False,
                "use_discounting": True,
                "alpha": 1.5,
                "checkpoint_frequency": 0
            },
            "parallelization": {
                "num_workers": 2,
                "chunk_size": 10
            }
        }
        
        simulation_id = self.create_test_simulation(config)
        if not simulation_id:
            return ValidationResult("nash_equilibrium", False, 0.0, {}, "Failed to create simulation")
        
        result = self.wait_for_completion(simulation_id)
        
        if result["status"] != "completed":
            return ValidationResult("nash_equilibrium", False, 0.0, {}, f"Simulation failed: {result.get('error', 'Unknown error')}")
        
        # Analyser les résultats
        final_exploitability = result.get("final_exploitability", 1.0)
        target_exploitability = config["solver_config"]["target_exploitability"]
        
        # Test de convergence
        converged = final_exploitability <= target_exploitability
        
        # Score basé sur la qualité de convergence
        if converged:
            score = 1.0 - (final_exploitability / target_exploitability) * 0.2
        else:
            score = max(0.0, 1.0 - (final_exploitability / target_exploitability))
        
        details = {
            "final_exploitability": final_exploitability,
            "target_exploitability": target_exploitability,
            "converged": converged,
            "iterations_completed": result.get("iterations_completed", 0),
            "convergence_time": result.get("convergence_time_seconds", 0)
        }
        
        return ValidationResult("nash_equilibrium", converged, score, details)
    
    def validate_strategy_consistency(self) -> ValidationResult:
        """Valide la cohérence des stratégies entre plusieurs runs"""
        
        base_config = {
            "name": "consistency_test",
            "description": "Test de cohérence des stratégies",
            "solver_type": "vanilla_cfr",
            "game_config": {
                "num_players": 2,
                "initial_stack": 1000,
                "small_blind": 5,
                "big_blind": 10,
                "ante": 0
            },
            "solver_config": {
                "max_iterations": 500,
                "target_exploitability": 0.01,
                "use_chance_sampling": False,
                "use_discounting": True,
                "alpha": 1.5,
                "checkpoint_frequency": 0
            },
            "parallelization": {
                "num_workers": 1,
                "chunk_size": 10
            }
        }
        
        results = []
        num_runs = 3
        
        for i in range(num_runs):
            config = base_config.copy()
            config["name"] = f"consistency_test_run_{i+1}"
            
            simulation_id = self.create_test_simulation(config)
            if not simulation_id:
                return ValidationResult("strategy_consistency", False, 0.0, {}, f"Failed to create simulation {i+1}")
            
            result = self.wait_for_completion(simulation_id)
            if result["status"] != "completed":
                return ValidationResult("strategy_consistency", False, 0.0, {}, f"Run {i+1} failed")
            
            results.append(result)
        
        # Analyser la cohérence
        exploitabilities = [r.get("final_exploitability", 1.0) for r in results]
        convergence_times = [r.get("convergence_time_seconds", 0) for r in results]
        
        # Calculer la variance relative
        if len(exploitabilities) > 1:
            mean_exploit = np.mean(exploitabilities)
            std_exploit = np.std(exploitabilities)
            coefficient_variation = std_exploit / mean_exploit if mean_exploit > 0 else 1.0
        else:
            coefficient_variation = 0.0
        
        # Test de cohérence (coefficient de variation < 10%)
        consistent = coefficient_variation < 0.1
        score = max(0.0, 1.0 - coefficient_variation * 5)  # Pénalité pour la variation
        
        details = {
            "exploitabilities": exploitabilities,
            "mean_exploitability": np.mean(exploitabilities),
            "std_exploitability": np.std(exploitabilities),
            "coefficient_variation": coefficient_variation,
            "convergence_times": convergence_times,
            "consistent": consistent
        }
        
        return ValidationResult("strategy_consistency", consistent, score, details)
    
    def validate_solver_comparison(self) -> ValidationResult:
        """Compare les différents solveurs CFR"""
        
        solvers = ["vanilla_cfr", "chance_sampling_cfr", "cfr_plus"]
        
        base_config = {
            "name": "solver_comparison",
            "description": "Comparaison des solveurs CFR",
            "game_config": {
                "num_players": 2,
                "initial_stack": 1000,
                "small_blind": 5,
                "big_blind": 10,
                "ante": 0
            },
            "solver_config": {
                "max_iterations": 300,
                "target_exploitability": 0.01,
                "use_chance_sampling": False,
                "use_discounting": True,
                "alpha": 1.5,
                "checkpoint_frequency": 0
            },
            "parallelization": {
                "num_workers": 1,
                "chunk_size": 10
            }
        }
        
        solver_results = {}
        
        for solver in solvers:
            config = base_config.copy()
            config["solver_type"] = solver
            config["name"] = f"solver_comparison_{solver}"
            
            if solver == "chance_sampling_cfr":
                config["solver_config"]["use_chance_sampling"] = True
            
            simulation_id = self.create_test_simulation(config)
            if not simulation_id:
                return ValidationResult("solver_comparison", False, 0.0, {}, f"Failed to create {solver} simulation")
            
            result = self.wait_for_completion(simulation_id)
            if result["status"] != "completed":
                return ValidationResult("solver_comparison", False, 0.0, {}, f"{solver} simulation failed")
            
            solver_results[solver] = result
        
        # Analyser les performances relatives
        exploitabilities = {solver: result.get("final_exploitability", 1.0) 
                          for solver, result in solver_results.items()}
        
        convergence_times = {solver: result.get("convergence_time_seconds", 0) 
                           for solver, result in solver_results.items()}
        
        # Tous les solveurs doivent converger vers des solutions similaires
        exploit_values = list(exploitabilities.values())
        if len(exploit_values) > 1:
            max_exploit = max(exploit_values)
            min_exploit = min(exploit_values)
            relative_difference = (max_exploit - min_exploit) / min_exploit if min_exploit > 0 else 1.0
        else:
            relative_difference = 0.0
        
        # Test de cohérence entre solveurs (différence relative < 20%)
        consistent = relative_difference < 0.2
        score = max(0.0, 1.0 - relative_difference * 2)
        
        details = {
            "solver_exploitabilities": exploitabilities,
            "solver_convergence_times": convergence_times,
            "relative_difference": relative_difference,
            "consistent_solutions": consistent,
            "best_solver": min(exploitabilities, key=exploitabilities.get),
            "fastest_solver": min(convergence_times, key=convergence_times.get)
        }
        
        return ValidationResult("solver_comparison", consistent, score, details)
    
    def validate_scalability(self) -> ValidationResult:
        """Valide la scalabilité avec différents nombres de workers"""
        
        worker_counts = [1, 2, 4]
        
        base_config = {
            "name": "scalability_test",
            "description": "Test de scalabilité",
            "solver_type": "cfr_plus",
            "game_config": {
                "num_players": 2,
                "initial_stack": 1000,
                "small_blind": 5,
                "big_blind": 10,
                "ante": 0
            },
            "solver_config": {
                "max_iterations": 400,
                "target_exploitability": 0.01,
                "use_chance_sampling": False,
                "use_discounting": True,
                "alpha": 1.5,
                "checkpoint_frequency": 0
            },
            "parallelization": {
                "chunk_size": 10
            }
        }
        
        scalability_results = {}
        
        for workers in worker_counts:
            config = base_config.copy()
            config["parallelization"]["num_workers"] = workers
            config["name"] = f"scalability_test_{workers}workers"
            
            simulation_id = self.create_test_simulation(config)
            if not simulation_id:
                return ValidationResult("scalability", False, 0.0, {}, f"Failed to create {workers}-worker simulation")
            
            result = self.wait_for_completion(simulation_id)
            if result["status"] != "completed":
                return ValidationResult("scalability", False, 0.0, {}, f"{workers}-worker simulation failed")
            
            scalability_results[workers] = result
        
        # Analyser l'amélioration de performance
        convergence_times = {workers: result.get("convergence_time_seconds", 0) 
                           for workers, result in scalability_results.items()}
        
        # Calculer l'efficacité de la parallélisation
        single_worker_time = convergence_times.get(1, 0)
        parallel_efficiencies = {}
        
        for workers, time_taken in convergence_times.items():
            if workers > 1 and single_worker_time > 0:
                theoretical_speedup = workers
                actual_speedup = single_worker_time / time_taken if time_taken > 0 else 0
                efficiency = actual_speedup / theoretical_speedup
                parallel_efficiencies[workers] = efficiency
        
        # Test de scalabilité (efficacité > 50% pour 2 workers, > 30% pour 4 workers)
        good_scalability = True
        min_efficiency = 1.0
        
        for workers, efficiency in parallel_efficiencies.items():
            expected_min_efficiency = 0.5 if workers == 2 else 0.3
            if efficiency < expected_min_efficiency:
                good_scalability = False
            min_efficiency = min(min_efficiency, efficiency)
        
        score = min_efficiency if parallel_efficiencies else 0.0
        
        details = {
            "convergence_times": convergence_times,
            "parallel_efficiencies": parallel_efficiencies,
            "good_scalability": good_scalability,
            "speedup_2workers": parallel_efficiencies.get(2, 0),
            "speedup_4workers": parallel_efficiencies.get(4, 0)
        }
        
        return ValidationResult("scalability", good_scalability, score, details)
    
    def run_comprehensive_validation(self) -> List[ValidationResult]:
        """Exécute une suite complète de tests de validation"""
        
        print("Starting comprehensive GTO strategy validation...")
        
        tests = [
            ("Nash Equilibrium Properties", self.validate_nash_equilibrium_properties),
            ("Strategy Consistency", self.validate_strategy_consistency),
            ("Solver Comparison", self.validate_solver_comparison),
            ("Scalability", self.validate_scalability)
        ]
        
        results = []
        
        for test_name, test_function in tests:
            print(f"\nRunning {test_name} test...")
            try:
                result = test_function()
                results.append(result)
                
                status = "✅ PASSED" if result.passed else "❌ FAILED"
                print(f"   {status} - Score: {result.score:.3f}")
                
                if result.error_message:
                    print(f"   Error: {result.error_message}")
                    
            except Exception as e:
                error_result = ValidationResult(test_name.lower().replace(" ", "_"), False, 0.0, {}, str(e))
                results.append(error_result)
                print(f"   ❌ FAILED - Exception: {e}")
        
        return results
    
    def generate_validation_report(self, results: List[ValidationResult]) -> None:
        """Génère un rapport de validation détaillé"""
        
        # Statistiques globales
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.passed)
        avg_score = np.mean([r.score for r in results])
        
        # Graphiques
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # Graphique 1: Résultats des tests
        test_names = [r.test_name.replace("_", " ").title() for r in results]
        test_scores = [r.score for r in results]
        colors = ['green' if r.passed else 'red' for r in results]
        
        ax1.bar(test_names, test_scores, color=colors, alpha=0.7)
        ax1.set_ylabel('Score')
        ax1.set_title('Validation Test Results')
        ax1.set_ylim(0, 1.1)
        ax1.tick_params(axis='x', rotation=45)
        
        # Graphique 2: Nash Equilibrium convergence
        nash_result = next((r for r in results if r.test_name == "nash_equilibrium"), None)
        if nash_result and nash_result.details:
            exploitability = nash_result.details.get("final_exploitability", 0)
            target = nash_result.details.get("target_exploitability", 0.001)
            
            ax2.bar(['Final', 'Target'], [exploitability, target], color=['blue', 'green'], alpha=0.7)
            ax2.set_ylabel('Exploitability')
            ax2.set_title('Nash Equilibrium Convergence')
            ax2.set_yscale('log')
        
        # Graphique 3: Solver comparison
        solver_result = next((r for r in results if r.test_name == "solver_comparison"), None)
        if solver_result and solver_result.details and "solver_exploitabilities" in solver_result.details:
            solvers = list(solver_result.details["solver_exploitabilities"].keys())
            exploits = list(solver_result.details["solver_exploitabilities"].values())
            
            ax3.bar(solvers, exploits, alpha=0.7)
            ax3.set_ylabel('Final Exploitability')
            ax3.set_title('Solver Performance Comparison')
            ax3.tick_params(axis='x', rotation=45)
        
        # Graphique 4: Scalabilité
        scalability_result = next((r for r in results if r.test_name == "scalability"), None)
        if scalability_result and scalability_result.details and "convergence_times" in scalability_result.details:
            workers = list(scalability_result.details["convergence_times"].keys())
            times = list(scalability_result.details["convergence_times"].values())
            
            ax4.plot(workers, times, 'o-', linewidth=2, markersize=8)
            ax4.set_xlabel('Number of Workers')
            ax4.set_ylabel('Convergence Time (s)')
            ax4.set_title('Scalability Performance')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / 'validation_results.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        # Rapport texte
        self._generate_validation_text_report(results, total_tests, passed_tests, avg_score)
    
    def _generate_validation_text_report(self, results: List[ValidationResult], 
                                       total_tests: int, passed_tests: int, avg_score: float) -> None:
        """Génère un rapport texte de validation"""
        
        report_path = self.results_dir / 'validation_report.md'
        
        with open(report_path, 'w') as f:
            f.write("# AlphaBetaSolver GTO Strategy Validation Report\n\n")
            f.write(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Executive Summary\n\n")
            f.write(f"- **Total Tests**: {total_tests}\n")
            f.write(f"- **Passed Tests**: {passed_tests}\n")
            f.write(f"- **Success Rate**: {passed_tests/total_tests*100:.1f}%\n")
            f.write(f"- **Average Score**: {avg_score:.3f}\n")
            f.write(f"- **Overall Status**: {'✅ SYSTEM VALIDATED' if passed_tests == total_tests else '⚠️ ISSUES DETECTED'}\n\n")
            
            f.write("## Detailed Test Results\n\n")
            
            for result in results:
                status_icon = "✅" if result.passed else "❌"
                f.write(f"### {status_icon} {result.test_name.replace('_', ' ').title()}\n\n")
                f.write(f"- **Status**: {'PASSED' if result.passed else 'FAILED'}\n")
                f.write(f"- **Score**: {result.score:.3f}\n")
                
                if result.error_message:
                    f.write(f"- **Error**: {result.error_message}\n")
                
                if result.details:
                    f.write("- **Details**:\n")
                    for key, value in result.details.items():
                        if isinstance(value, float):
                            f.write(f"  - {key}: {value:.6f}\n")
                        elif isinstance(value, dict):
                            f.write(f"  - {key}: {json.dumps(value, indent=4)}\n")
                        else:
                            f.write(f"  - {key}: {value}\n")
                
                f.write("\n")
            
            # Recommandations
            f.write("## Validation Summary & Recommendations\n\n")
            
            if passed_tests == total_tests:
                f.write("🎉 **Congratulations!** All validation tests passed successfully.\n\n")
                f.write("Your AlphaBetaSolver implementation demonstrates:\n")
                f.write("- Correct Nash equilibrium convergence\n")
                f.write("- Consistent strategy computation\n")
                f.write("- Reliable solver algorithms\n")
                f.write("- Good scalability characteristics\n\n")
                f.write("The system is **ready for production use**.\n\n")
            else:
                f.write("⚠️ **Issues Detected** - Some validation tests failed.\n\n")
                
                failed_tests = [r for r in results if not r.passed]
                f.write("**Failed Tests:**\n")
                for test in failed_tests:
                    f.write(f"- {test.test_name}: {test.error_message or 'See details above'}\n")
                
                f.write("\n**Recommended Actions:**\n")
                f.write("1. Review failed test details above\n")
                f.write("2. Check algorithm implementations\n")
                f.write("3. Verify system configuration\n")
                f.write("4. Re-run tests after fixes\n\n")
            
            # Performance insights
            f.write("## Performance Insights\n\n")
            
            nash_result = next((r for r in results if r.test_name == "nash_equilibrium"), None)
            if nash_result and nash_result.details:
                f.write(f"- **Nash Convergence**: {nash_result.details.get('final_exploitability', 'N/A'):.6f} exploitability\n")
                f.write(f"- **Convergence Time**: {nash_result.details.get('convergence_time', 0):.2f} seconds\n")
            
            solver_result = next((r for r in results if r.test_name == "solver_comparison"), None)
            if solver_result and solver_result.details:
                best_solver = solver_result.details.get("best_solver", "N/A")
                fastest_solver = solver_result.details.get("fastest_solver", "N/A")
                f.write(f"- **Best Solver**: {best_solver}\n")
                f.write(f"- **Fastest Solver**: {fastest_solver}\n")
            
            f.write("\n")
            
        print(f"Validation report generated: {report_path}")

def main():
    """Point d'entrée principal"""
    
    validator = GTOStrategyValidator()
    
    # Vérifier que l'API est accessible
    try:
        response = requests.get(f"{validator.api_base_url}/health", timeout=5)
        if response.status_code != 200:
            print("❌ API is not accessible")
            print("Please ensure the master node is running:")
            print("cd /Users/bastienjavaux/Desktop/AlphaBetaSolver/backend/python && python start_master.py")
            return 1
    except Exception:
        print("❌ API is not accessible")
        return 1
    
    print("✅ API is accessible")
    
    # Exécuter la validation complète
    print("\nStarting comprehensive validation (this may take 10-15 minutes)...")
    results = validator.run_comprehensive_validation()
    
    # Générer le rapport
    print("\nGenerating validation report...")
    validator.generate_validation_report(results)
    
    # Résumé final
    passed_tests = sum(1 for r in results if r.passed)
    total_tests = len(results)
    
    print(f"\nValidation completed!")
    print(f"Results: {passed_tests}/{total_tests} tests passed")
    print(f"Reports saved in: {validator.results_dir}")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! System is validated and ready for production.")
        return 0
    else:
        print("⚠️ Some tests failed. Check the validation report for details.")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
