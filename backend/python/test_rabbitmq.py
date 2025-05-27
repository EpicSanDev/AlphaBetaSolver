#!/usr/bin/env python3
"""
Test script to verify RabbitMQ connection from local Python environment.
"""

import asyncio
import aio_pika


async def test_rabbitmq_connection():
    """Test connection to RabbitMQ."""
    try:
        # Using the same credentials as in docker-compose
        rabbitmq_url = "amqp://gto_user:gto_password@localhost:5672/"
        print(f"Attempting to connect to: {rabbitmq_url}")

        connection = await aio_pika.connect_robust(rabbitmq_url)
        print("✅ Successfully connected to RabbitMQ!")

        channel = await connection.channel()
        print("✅ Channel created successfully!")

        # Test declaring a queue
        queue = await channel.declare_queue("test_queue", durable=True)
        print(f"✅ Queue declared: {queue.name}")

        await connection.close()
        print("✅ Connection closed cleanly")

        return True

    except Exception as e:
        print(f"❌ Error connecting to RabbitMQ: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_rabbitmq_connection())
    exit(0 if success else 1)
