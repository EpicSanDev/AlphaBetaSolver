import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
export let errorRate = new Rate('errors');

// Test configuration
export let options = {
  stages: [
    { duration: '2m', target: 10 }, // Ramp up to 10 users
    { duration: '5m', target: 10 }, // Stay at 10 users
    { duration: '2m', target: 20 }, // Ramp up to 20 users
    { duration: '5m', target: 20 }, // Stay at 20 users
    { duration: '2m', target: 0 },  // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'], // 95% of requests must complete below 500ms
    http_req_failed: ['rate<0.1'],    // Error rate must be below 10%
    errors: ['rate<0.1'],             // Custom error rate must be below 10%
  },
};

const BASE_URL = 'http://localhost:8000';

// Test data
const testGameState = {
  board: ['As', 'Kh', 'Qd'],
  pot_size: 100,
  stack_sizes: [1000, 1000],
  position: 'BTN',
  betting_round: 'flop',
  actions: [
    { player: 0, action: 'bet', amount: 50 },
    { player: 1, action: 'call', amount: 50 }
  ]
};

export function setup() {
  console.log('Starting GTO Poker Solver Load Test');
  
  // Check if API is available
  let response = http.get(`${BASE_URL}/api/v1/health`);
  if (response.status !== 200) {
    throw new Error('API is not available');
  }
  
  console.log('API is ready for testing');
}

export default function () {
  // Test 1: Health check
  let healthResponse = http.get(`${BASE_URL}/api/v1/health`);
  check(healthResponse, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 100ms': (r) => r.timings.duration < 100,
  }) || errorRate.add(1);

  sleep(1);

  // Test 2: Get simulations list
  let simulationsResponse = http.get(`${BASE_URL}/api/v1/simulations`);
  check(simulationsResponse, {
    'simulations list status is 200': (r) => r.status === 200,
    'simulations list response time < 200ms': (r) => r.timings.duration < 200,
  }) || errorRate.add(1);

  sleep(1);

  // Test 3: Create simulation
  let createResponse = http.post(
    `${BASE_URL}/api/v1/simulations`,
    JSON.stringify({
      name: `Load Test Simulation ${Date.now()}`,
      game_state: testGameState,
      solver_config: {
        iterations: 100,
        accuracy_threshold: 0.01,
        use_compression: true
      }
    }),
    {
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );

  let simulationId;
  if (check(createResponse, {
    'create simulation status is 201': (r) => r.status === 201,
    'create simulation response time < 1000ms': (r) => r.timings.duration < 1000,
  })) {
    let createData = JSON.parse(createResponse.body);
    simulationId = createData.simulation_id;
  } else {
    errorRate.add(1);
  }

  sleep(2);

  // Test 4: Get simulation status (if creation was successful)
  if (simulationId) {
    let statusResponse = http.get(`${BASE_URL}/api/v1/simulations/${simulationId}/status`);
    check(statusResponse, {
      'simulation status is 200': (r) => r.status === 200,
      'simulation status response time < 300ms': (r) => r.timings.duration < 300,
    }) || errorRate.add(1);

    sleep(1);

    // Test 5: Cancel simulation to clean up
    let cancelResponse = http.del(`${BASE_URL}/api/v1/simulations/${simulationId}`);
    check(cancelResponse, {
      'cancel simulation status is 200': (r) => r.status === 200,
    }) || errorRate.add(1);
  }

  sleep(1);
}

export function teardown() {
  console.log('Load test completed');
}
