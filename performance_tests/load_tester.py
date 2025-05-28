#!/usr/bin/env python3
"""
Load test for the distributed AlphaBetaSolver system
Tests scalability, reliability, and performance under load
"""

import asyncio
import aiohttp
import time
import json
import random
import concurrent.futures
import threading
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

@dataclass
class LoadTestResult:
    """Résultat d'un test de charge"""
    test_name: str
    concurrent_requests: int
    total_requests: int
    success_rate: float
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    throughput_rps: float
    errors: List[str]

class AlphaBetaSolverLoadTester:
    """Test de charge pour le système distribué AlphaBetaSolver"""
    
    def __init__(self, base_url: str = "http://localhost:8002"):
        self.base_url = base_url
        self.results_dir = Path(__file__).parent / "load_test_results"
        self.results_dir.mkdir(exist_ok=True)
        
    async def health_check(self) -> bool:
        """Vérifie que l'API est accessible"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    return response.status == 200
        except Exception:
            return False
    
    async def create_simulation(self, session: aiohttp.ClientSession, 
                              simulation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Crée une simulation via l'API"""
        async with session.post(
            f"{self.base_url}/api/v1/simulations", 
            json=simulation_config
        ) as response:
            return {
                "status": response.status,
                "data": await response.json() if response.status == 200 else None,
                "response_time": time.time()
            }
    
    async def get_simulation_status(self, session: aiohttp.ClientSession, 
                                  simulation_id: str) -> Dict[str, Any]:
        """Récupère le statut d'une simulation"""
        async with session.get(
            f"{self.base_url}/api/v1/simulations/{simulation_id}"
        ) as response:
            return {
                "status": response.status,
                "data": await response.json() if response.status == 200 else None,
                "response_time": time.time()
            }
    
    def generate_random_simulation_config(self) -> Dict[str, Any]:
        """Génère une configuration de simulation aléatoire"""
        
        solvers = ["vanilla_cfr", "chance_sampling_cfr", "cfr_plus"]
        
        return {
            "name": f"load_test_sim_{random.randint(1000, 9999)}",
            "description": "Simulation générée pour test de charge",
            "solver_type": random.choice(solvers),
            "game_config": {
                "num_players": 2,
                "initial_stack": random.randint(500, 2000),
                "small_blind": 5,
                "big_blind": 10,
                "ante": 0
            },
            "solver_config": {
                "max_iterations": random.randint(50, 500),
                "target_exploitability": random.uniform(0.001, 0.01),
                "use_chance_sampling": random.choice([True, False]),
                "use_discounting": True,
                "alpha": random.uniform(1.0, 2.0),
                "beta": 0.0,
                "checkpoint_frequency": 0
            },
            "parallelization": {
                "num_workers": random.randint(1, 4),
                "chunk_size": random.randint(5, 20)
            }
        }
    
    async def run_concurrent_simulations(self, num_concurrent: int, 
                                       total_requests: int) -> LoadTestResult:
        """Exécute des simulations concurrentes"""
        
        print(f"Running {total_requests} requests with {num_concurrent} concurrent connections...")
        
        semaphore = asyncio.Semaphore(num_concurrent)
        response_times = []
        errors = []
        successful_requests = 0
        
        async def single_request():
            nonlocal successful_requests
            async with semaphore:
                try:
                    start_time = time.time()
                    config = self.generate_random_simulation_config()
                    
                    async with aiohttp.ClientSession() as session:
                        result = await self.create_simulation(session, config)
                        
                    end_time = time.time()
                    response_time = end_time - start_time
                    
                    if result["status"] == 200:
                        successful_requests += 1
                        response_times.append(response_time)
                    else:
                        errors.append(f"HTTP {result['status']}")
                        
                except Exception as e:
                    errors.append(str(e))
        
        # Mesurer le débit
        start_test_time = time.time()
        
        # Exécuter toutes les requêtes
        tasks = [single_request() for _ in range(total_requests)]
        await asyncio.gather(*tasks)
        
        end_test_time = time.time()
        total_test_time = end_test_time - start_test_time
        
        # Calculer les métriques
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        avg_response_time = np.mean(response_times) if response_times else 0
        p95_response_time = np.percentile(response_times, 95) if response_times else 0
        p99_response_time = np.percentile(response_times, 99) if response_times else 0
        throughput_rps = successful_requests / total_test_time if total_test_time > 0 else 0
        
        return LoadTestResult(
            test_name=f"concurrent_simulations_{num_concurrent}x{total_requests}",
            concurrent_requests=num_concurrent,
            total_requests=total_requests,
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            throughput_rps=throughput_rps,
            errors=errors[:10]  # Garder seulement les 10 premières erreurs
        )
    
    async def run_sustained_load_test(self, requests_per_second: int, 
                                    duration_seconds: int) -> LoadTestResult:
        """Test de charge soutenue"""
        
        print(f"Running sustained load test: {requests_per_second} RPS for {duration_seconds}s...")
        
        interval = 1.0 / requests_per_second
        end_time = time.time() + duration_seconds
        
        response_times = []
        errors = []
        successful_requests = 0
        total_requests = 0
        
        async with aiohttp.ClientSession() as session:
            while time.time() < end_time:
                start_time = time.time()
                total_requests += 1
                
                try:
                    config = self.generate_random_simulation_config()
                    result = await self.create_simulation(session, config)
                    
                    response_time = time.time() - start_time
                    
                    if result["status"] == 200:
                        successful_requests += 1
                        response_times.append(response_time)
                    else:
                        errors.append(f"HTTP {result['status']}")
                        
                except Exception as e:
                    errors.append(str(e))
                
                # Respecter le débit souhaité
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
        
        # Calculer les métriques
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        avg_response_time = np.mean(response_times) if response_times else 0
        p95_response_time = np.percentile(response_times, 95) if response_times else 0
        p99_response_time = np.percentile(response_times, 99) if response_times else 0
        throughput_rps = successful_requests / duration_seconds
        
        return LoadTestResult(
            test_name=f"sustained_load_{requests_per_second}rps_{duration_seconds}s",
            concurrent_requests=1,
            total_requests=total_requests,
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            throughput_rps=throughput_rps,
            errors=errors[:10]
        )
    
    async def run_simulation_lifecycle_test(self, num_simulations: int) -> LoadTestResult:
        """Test du cycle de vie complet des simulations"""
        
        print(f"Running simulation lifecycle test with {num_simulations} simulations...")
        
        response_times = []
        errors = []
        successful_lifecycles = 0
        
        async with aiohttp.ClientSession() as session:
            for i in range(num_simulations):
                try:
                    start_time = time.time()
                    
                    # Créer la simulation
                    config = self.generate_random_simulation_config()
                    config["solver_config"]["max_iterations"] = 50  # Rapide pour les tests
                    
                    create_result = await self.create_simulation(session, config)
                    
                    if create_result["status"] != 200:
                        errors.append(f"Create failed: HTTP {create_result['status']}")
                        continue
                    
                    simulation_id = create_result["data"]["simulation_id"]
                    
                    # Attendre que la simulation se termine
                    max_wait = 30  # 30 secondes max
                    check_interval = 1  # Vérifier chaque seconde
                    wait_time = 0
                    
                    while wait_time < max_wait:
                        status_result = await self.get_simulation_status(session, simulation_id)
                        
                        if status_result["status"] != 200:
                            errors.append(f"Status check failed: HTTP {status_result['status']}")
                            break
                        
                        status = status_result["data"]["status"]
                        
                        if status in ["completed", "failed", "error"]:
                            if status == "completed":
                                successful_lifecycles += 1
                                response_times.append(time.time() - start_time)
                            else:
                                errors.append(f"Simulation {status}: {simulation_id}")
                            break
                        
                        await asyncio.sleep(check_interval)
                        wait_time += check_interval
                    
                    else:
                        errors.append(f"Simulation timeout: {simulation_id}")
                    
                except Exception as e:
                    errors.append(str(e))
        
        # Calculer les métriques
        success_rate = successful_lifecycles / num_simulations if num_simulations > 0 else 0
        avg_response_time = np.mean(response_times) if response_times else 0
        p95_response_time = np.percentile(response_times, 95) if response_times else 0
        p99_response_time = np.percentile(response_times, 99) if response_times else 0
        throughput_rps = successful_lifecycles / (max(response_times) if response_times else 1)
        
        return LoadTestResult(
            test_name=f"simulation_lifecycle_{num_simulations}",
            concurrent_requests=1,
            total_requests=num_simulations,
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            throughput_rps=throughput_rps,
            errors=errors[:10]
        )
    
    async def run_comprehensive_load_tests(self) -> List[LoadTestResult]:
        """Exécute une suite complète de tests de charge"""
        
        print("Starting comprehensive load tests...")
        
        results = []
        
        # Test 1: Concurrence croissante
        print("\n1. Testing increasing concurrency...")
        for concurrency in [1, 5, 10, 20, 50]:
            result = await self.run_concurrent_simulations(concurrency, 20)
            results.append(result)
            print(f"   {concurrency} concurrent: {result.success_rate:.1%} success, "
                  f"{result.avg_response_time:.2f}s avg response time")
        
        # Test 2: Charge soutenue
        print("\n2. Testing sustained load...")
        for rps in [1, 2, 5, 10]:
            result = await self.run_sustained_load_test(rps, 30)
            results.append(result)
            print(f"   {rps} RPS: {result.success_rate:.1%} success, "
                  f"{result.throughput_rps:.2f} actual RPS")
        
        # Test 3: Cycle de vie des simulations
        print("\n3. Testing simulation lifecycles...")
        result = await self.run_simulation_lifecycle_test(10)
        results.append(result)
        print(f"   Lifecycle test: {result.success_rate:.1%} success, "
              f"{result.avg_response_time:.2f}s avg completion time")
        
        return results
    
    def generate_load_test_report(self, results: List[LoadTestResult]) -> None:
        """Génère un rapport détaillé des tests de charge"""
        
        # Graphiques
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # Graphique 1: Taux de succès vs Concurrence
        concurrent_tests = [r for r in results if "concurrent_simulations" in r.test_name]
        if concurrent_tests:
            concurrency = [r.concurrent_requests for r in concurrent_tests]
            success_rates = [r.success_rate * 100 for r in concurrent_tests]
            ax1.plot(concurrency, success_rates, 'o-', linewidth=2, markersize=8)
            ax1.set_xlabel('Concurrent Requests')
            ax1.set_ylabel('Success Rate (%)')
            ax1.set_title('Success Rate vs Concurrency')
            ax1.grid(True, alpha=0.3)
            ax1.set_ylim(0, 105)
        
        # Graphique 2: Temps de réponse vs Concurrence
        if concurrent_tests:
            response_times = [r.avg_response_time for r in concurrent_tests]
            p95_times = [r.p95_response_time for r in concurrent_tests]
            ax2.plot(concurrency, response_times, 'o-', label='Average', linewidth=2, markersize=8)
            ax2.plot(concurrency, p95_times, 's-', label='P95', linewidth=2, markersize=8)
            ax2.set_xlabel('Concurrent Requests')
            ax2.set_ylabel('Response Time (seconds)')
            ax2.set_title('Response Time vs Concurrency')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
        
        # Graphique 3: Débit vs Charge demandée
        sustained_tests = [r for r in results if "sustained_load" in r.test_name]
        if sustained_tests:
            requested_rps = []
            actual_rps = []
            for r in sustained_tests:
                parts = r.test_name.split('_')
                requested_rps.append(int(parts[2].replace('rps', '')))
                actual_rps.append(r.throughput_rps)
            
            ax3.plot(requested_rps, actual_rps, 'o-', linewidth=2, markersize=8, label='Actual')
            ax3.plot(requested_rps, requested_rps, '--', alpha=0.7, label='Ideal')
            ax3.set_xlabel('Requested RPS')
            ax3.set_ylabel('Actual RPS')
            ax3.set_title('Throughput: Requested vs Actual')
            ax3.grid(True, alpha=0.3)
            ax3.legend()
        
        # Graphique 4: Distribution des temps de réponse
        all_response_times = []
        for r in results:
            if r.avg_response_time > 0:
                all_response_times.extend([r.avg_response_time, r.p95_response_time, r.p99_response_time])
        
        if all_response_times:
            ax4.hist(all_response_times, bins=20, alpha=0.7, edgecolor='black')
            ax4.set_xlabel('Response Time (seconds)')
            ax4.set_ylabel('Frequency')
            ax4.set_title('Response Time Distribution')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / 'load_test_results.png', dpi=300, bbox_inches='tight')
        plt.show()
        
        # Rapport texte
        self._generate_load_test_text_report(results)
    
    def _generate_load_test_text_report(self, results: List[LoadTestResult]) -> None:
        """Génère un rapport texte des tests de charge"""
        
        report_path = self.results_dir / 'load_test_report.md'
        
        with open(report_path, 'w') as f:
            f.write("# AlphaBetaSolver Load Test Report\n\n")
            f.write(f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Executive Summary\n\n")
            
            # Calculer les métriques globales
            total_requests = sum(r.total_requests for r in results)
            avg_success_rate = np.mean([r.success_rate for r in results]) * 100
            max_throughput = max(r.throughput_rps for r in results)
            
            f.write(f"- **Total Requests Tested**: {total_requests}\n")
            f.write(f"- **Average Success Rate**: {avg_success_rate:.1f}%\n")
            f.write(f"- **Maximum Throughput**: {max_throughput:.2f} RPS\n\n")
            
            # Détails par test
            f.write("## Detailed Test Results\n\n")
            
            for result in results:
                f.write(f"### {result.test_name}\n\n")
                f.write(f"- **Success Rate**: {result.success_rate*100:.1f}%\n")
                f.write(f"- **Average Response Time**: {result.avg_response_time:.3f}s\n")
                f.write(f"- **P95 Response Time**: {result.p95_response_time:.3f}s\n")
                f.write(f"- **P99 Response Time**: {result.p99_response_time:.3f}s\n")
                f.write(f"- **Throughput**: {result.throughput_rps:.2f} RPS\n")
                f.write(f"- **Total Requests**: {result.total_requests}\n")
                
                if result.errors:
                    f.write(f"- **Sample Errors**: {', '.join(result.errors[:5])}\n")
                
                f.write("\n")
            
            # Recommandations
            f.write("## Performance Recommendations\n\n")
            
            # Analyser les résultats pour des recommandations
            concurrent_tests = [r for r in results if "concurrent_simulations" in r.test_name]
            
            if concurrent_tests:
                # Trouver le point de saturation
                good_performance = [r for r in concurrent_tests if r.success_rate > 0.95 and r.avg_response_time < 5.0]
                if good_performance:
                    max_good_concurrency = max(r.concurrent_requests for r in good_performance)
                    f.write(f"1. **Recommended Maximum Concurrency**: {max_good_concurrency} concurrent requests\n")
                
                # Analyser la dégradation
                degraded = [r for r in concurrent_tests if r.success_rate < 0.9]
                if degraded:
                    min_degraded_concurrency = min(r.concurrent_requests for r in degraded)
                    f.write(f"2. **Performance Degradation Starts**: Around {min_degraded_concurrency} concurrent requests\n")
            
            sustained_tests = [r for r in results if "sustained_load" in r.test_name]
            if sustained_tests:
                max_sustainable_rps = max(r.throughput_rps for r in sustained_tests if r.success_rate > 0.95)
                f.write(f"3. **Maximum Sustainable Throughput**: {max_sustainable_rps:.2f} RPS\n")
            
            f.write("\n4. **System Optimization Suggestions**:\n")
            f.write("   - Consider implementing connection pooling\n")
            f.write("   - Add caching for frequent calculations\n")
            f.write("   - Implement request rate limiting\n")
            f.write("   - Consider horizontal scaling of compute agents\n")
            f.write("   - Monitor and optimize database queries\n\n")
            
        print(f"Load test report generated: {report_path}")

async def main():
    """Point d'entrée principal"""
    
    tester = AlphaBetaSolverLoadTester()
    
    # Vérifier que l'API est accessible
    print("Checking API health...")
    if not await tester.health_check():
        print("❌ API is not accessible at http://localhost:8002")
        print("Please ensure the master node is running:")
        print("cd /Users/bastienjavaux/Desktop/AlphaBetaSolver/backend/python && python start_master.py")
        return 1
    
    print("✅ API is accessible")
    
    # Exécuter les tests de charge
    print("\nStarting load tests (this may take several minutes)...")
    results = await tester.run_comprehensive_load_tests()
    
    # Générer le rapport
    print("\nGenerating load test report...")
    tester.generate_load_test_report(results)
    
    print("\nLoad tests completed!")
    print(f"Results saved in: {tester.results_dir}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
