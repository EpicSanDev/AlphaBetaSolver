#!/usr/bin/env python3
"""
Debug WebSocket connectivity to identify 403 error cause
"""

import asyncio
import websockets
import json

async def test_websocket_direct():
    """Test WebSocket connection directly to master-node container"""
    uri = "ws://localhost:8000/ws"
    print(f"Testing direct connection to {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Direct connection successful!")
            await websocket.send(json.dumps({"type": "ping"}))
            response = await websocket.recv()
            print(f"Response: {response}")
    except Exception as e:
        print(f"❌ Direct connection failed: {e}")

async def test_websocket_via_nginx():
    """Test WebSocket connection via nginx proxy"""
    uri = "ws://localhost/ws"
    print(f"Testing nginx proxy connection to {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Nginx proxy connection successful!")
            await websocket.send(json.dumps({"type": "ping"}))
            response = await websocket.recv()
            print(f"Response: {response}")
    except Exception as e:
        print(f"❌ Nginx proxy connection failed: {e}")

async def test_websocket_test_endpoint():
    """Test the simple WebSocket test endpoint"""
    uri = "ws://localhost:8000/ws-test"
    print(f"Testing simple test endpoint {uri}")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Test endpoint connection successful!")
            response = await websocket.recv()
            print(f"Response: {response}")
    except Exception as e:
        print(f"❌ Test endpoint connection failed: {e}")

async def main():
    print("WebSocket Connectivity Debug Tool")
    print("=" * 40)
    
    await test_websocket_direct()
    print()
    await test_websocket_test_endpoint()
    print()
    await test_websocket_via_nginx()

if __name__ == "__main__":
    asyncio.run(main())
