#!/usr/bin/env python3
"""
WebSocket message format tester to debug JSON parse errors
"""

import asyncio
import websockets
import json
import argparse

async def test_websocket_formats(uri):
    """Test different message formats with WebSocket"""
    print(f"Testing WebSocket message formats on {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connection successful!")
            
            # Test 1: Plain string
            print("\n[Test 1] Sending plain string")
            await websocket.send("Connection test")
            response = await websocket.recv()
            print(f"Response: {response}")
            
            # Test 2: JSON object with type ping
            print("\n[Test 2] Sending JSON ping")
            await websocket.send(json.dumps({"type": "ping"}))
            response = await websocket.recv()
            print(f"Response: {response}")
            
            # Test 3: Echo with string prefix
            print("\n[Test 3] Sending Echo with JSON")
            await websocket.send(f"Echo: {json.dumps({'type': 'echo', 'message': 'hello'})}")
            response = await websocket.recv()
            print(f"Response: {response}")
            
            # Test 4: Subscribe to system updates
            print("\n[Test 4] Subscribing to system updates")
            await websocket.send(json.dumps({"type": "subscribe_system"}))
            response = await websocket.recv()
            print(f"Response: {response}")
            
            # Wait for any additional messages
            print("\nWaiting for any additional messages (10 seconds)...")
            for _ in range(5):
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2)
                    print(f"Additional message: {response}")
                except asyncio.TimeoutError:
                    print("No more messages")
                    break
    
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebSocket message format tester")
    parser.add_argument("--uri", default="ws://localhost:8000/ws", help="WebSocket URI to test")
    args = parser.parse_args()
    
    asyncio.run(test_websocket_formats(args.uri))
