import asyncio
import argparse
import signal
import sys
from typing import Dict, Any, List, Optional

import httpx

from mediator import MediatorService
from requestor_bot import RequestorBot
from provider_bot import ProviderBot
from models import ServiceCategory, get_dict
from models import ServiceRequest, ServiceFormat

# Demo bot configurations
BOTS_CONFIG = {
    "mediator": {
        "host": "localhost",
        "port": 8100
    },
    "ai_news_bot": {
        "name": "AI News Bot",
        "description": "Provides the latest news and trends in AI",
        "type": "provider",
        "capabilities": [ServiceCategory.AI, ServiceCategory.NEWS],
        "host": "localhost",
        "port": 8001
    },
    "finance_bot": {
        "name": "Finance Data Bot",
        "description": "Provides financial data including stock prices and market analysis",
        "type": "provider",
        "capabilities": [ServiceCategory.FINANCE],
        "host": "localhost",
        "port": 8002
    },
    "data_requestor": {
        "name": "Data Requestor Bot",
        "description": "Requests various types of data from provider bots",
        "type": "requestor",
        "host": "localhost",
        "port": 8003
    }
}


async def run_mediator():
    """Run the mediator service"""
    config = BOTS_CONFIG["mediator"]
    mediator = MediatorService(host=config["host"], port=config["port"])
    await mediator.start()


async def run_ai_news_bot():
    """Run the AI news provider bot"""
    config = BOTS_CONFIG["ai_news_bot"]
    mediator_config = BOTS_CONFIG["mediator"]

    bot = ProviderBot(
        name=config["name"],
        description=config["description"],
        capabilities=config["capabilities"],
        host=config["host"],
        port=config["port"],
        mediator_url=f"http://{mediator_config['host']}:{mediator_config['port']}"
    )

    await bot.start()


async def run_finance_bot():
    """Run the finance provider bot"""
    config = BOTS_CONFIG["finance_bot"]
    mediator_config = BOTS_CONFIG["mediator"]

    bot = ProviderBot(
        name=config["name"],
        description=config["description"],
        capabilities=config["capabilities"],
        host=config["host"],
        port=config["port"],
        mediator_url=f"http://{mediator_config['host']}:{mediator_config['port']}"
    )

    await bot.start()


async def run_requestor_bot():
    """Run the data requestor bot"""
    config = BOTS_CONFIG["data_requestor"]
    mediator_config = BOTS_CONFIG["mediator"]

    bot = RequestorBot(
        name=config["name"],
        description=config["description"],
        host=config["host"],
        port=config["port"],
        mediator_url=f"http://{mediator_config['host']}:{mediator_config['port']}"
    )

    await bot.start()


async def run_demo_scenario():
    """Run a demo scenario with the bot marketplace"""
    print("Starting demo scenario for AI Bot Marketplace")

    # Wait for services to start up
    print("Waiting for services to start...")
    await asyncio.sleep(5)

    mediator_config = BOTS_CONFIG["mediator"]
    mediator_url = f"http://{mediator_config['host']}:{mediator_config['port']}"

    # Instead of creating a temporary requestor, use an existing one
    requestor_config = BOTS_CONFIG["data_requestor"]
    requestor_url = f"http://{requestor_config['host']}:{requestor_config['port']}"

    # Discover available bots directly through mediator API
    print("\n=== Discovering available bots ===")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{mediator_url}/bots")
        if response.status_code == 200:
            bots = response.json()
            for bot in bots:
                print(f"- {bot['name']} ({bot['type']}): {bot['description']}")

    # First scenario: request AI trends
    print("\n=== SCENARIO 1: Requesting AI trends ===")
    print("Sending request for latest AI trends...")

    # Create an AI trends request
    request = ServiceRequest(
        requestor_id="demo-requestor-id",  # Use a fixed ID for demo
        category=ServiceCategory.AI,
        description="Provide the latest trends in AI technology with popularity metrics",
        required_format=ServiceFormat.JSON,
        response_schema=None,  # Using the fixed field name
        parameters={},
        ttl=3600
    )

    # Publish request to mediator
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{mediator_url}/requests/publish",
            json=get_dict(request)
        )

        if response.status_code == 200:
            result = response.json()
            request_id = result["request_id"]
            print(f"Request created with ID: {request_id}")

            # Broadcast the request to all provider bots
            print(f"Broadcasting request {request_id} to all provider bots")
            provider_bots = [bot for bot in bots if bot["type"] == "provider"]
            for bot in provider_bots:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{bot['api_endpoint']}/request",
                            json=get_dict(request)
                        )
                        print(f"Broadcast to {bot['name']}: {response.status_code}")
                except Exception as e:
                    print(f"Error broadcasting to {bot['name']}: {e}")

            # Wait for responses
            print("Waiting for responses...")
            await asyncio.sleep(10)  # Give more time for responses

            # Get all providers from their api_endpoint/services/{service_id}
            ai_services = []
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{mediator_url}/services",
                    params={"category": "ai"}
                )

                if response.status_code == 200:
                    ai_services = response.json()

            if ai_services:
                print("\nReceived response(s):")
                for i, service in enumerate(ai_services):
                    print(f"\nService from provider {i + 1}:")
                    print(f"- {service['name']}")
                    print(f"- Endpoint: {service['endpoint']}")

                    # Try to get the data from the endpoint
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(service['endpoint'])

                            if response.status_code == 200:
                                data = response.json()
                                print(f"\nData preview:")
                                if 'trends' in data:
                                    for trend in data['trends'][:3]:  # Show first 3 trends
                                        print(
                                            f"- {trend['trend_name']} ({trend['popularity']}%): {trend['description']}")
                                else:
                                    print(data)
                    except Exception as e:
                        print(f"Error getting data: {e}")
            else:
                print("No AI services found")

    # Second scenario: request financial data
    print("\n=== SCENARIO 2: Requesting financial data ===")
    print("Sending request for financial data about Apple stock...")

    # Create a financial data request
    request = ServiceRequest(
        requestor_id="demo-requestor-id",  # Use a fixed ID for demo
        category=ServiceCategory.FINANCE,
        description="Provide AAPL (Apple) stock data for the last quarter with daily open, close, high, low prices and volume",
        required_format=ServiceFormat.JSON,
        response_schema=None,  # Using the fixed field name
        parameters={},
        ttl=3600
    )

    # Publish request to mediator
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{mediator_url}/requests/publish",
            json=get_dict(request)
        )

        if response.status_code == 200:
            result = response.json()
            request_id = result["request_id"]
            print(f"Request created with ID: {request_id}")

            # Broadcast the request to all provider bots
            print(f"Broadcasting request {request_id} to all provider bots")
            finance_bots = [bot for bot in bots if "finance" in [c.lower() for c in bot.get("capabilities", [])]]
            for bot in finance_bots:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{bot['api_endpoint']}/request",
                            json=get_dict(request)
                        )
                        print(f"Broadcast to {bot['name']}: {response.status_code}")
                except Exception as e:
                    print(f"Error broadcasting to {bot['name']}: {e}")

            # Wait for responses
            print("Waiting for responses...")
            await asyncio.sleep(10)  # Give more time for responses

            # Get all providers from their api_endpoint/services/{service_id}
            finance_services = []
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{mediator_url}/services",
                    params={"category": "finance"}
                )

                if response.status_code == 200:
                    finance_services = response.json()

            if finance_services:
                print("\nReceived response(s):")
                for i, service in enumerate(finance_services):
                    print(f"\nService from provider {i + 1}:")
                    print(f"- {service['name']}")
                    print(f"- Endpoint: {service['endpoint']}")

                    # Try to get the data from the endpoint
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(service['endpoint'])

                            if response.status_code == 200:
                                data = response.json()
                                print(f"\nData preview:")
                                if 'symbol' in data:
                                    print(f"Stock: {data['name']} ({data['symbol']})")
                                    print(f"Period: {data['period']}")
                                    print(f"Sample data (first 3 days):")
                                    for day in data['data'][:3]:  # Show first 3 days
                                        print(
                                            f"- {day['date']}: Open ${day['open']}, Close ${day['close']}, Volume {day['volume']}")
                                else:
                                    print(data)
                    except Exception as e:
                        print(f"Error getting data: {e}")
            else:
                print("No finance services found")

    print("\n=== Demo scenario completed ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI-driven Bot Marketplace")
    parser.add_argument("--component", choices=["mediator", "ai_news", "finance", "requestor", "demo"],
                        help="Component to run")

    args = parser.parse_args()


    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print('Shutting down...')
        sys.exit(0)


    signal.signal(signal.SIGINT, signal_handler)

    # Run the selected component
    if args.component == "mediator":
        asyncio.run(run_mediator())
    elif args.component == "ai_news":
        asyncio.run(run_ai_news_bot())
    elif args.component == "finance":
        asyncio.run(run_finance_bot())
    elif args.component == "requestor":
        asyncio.run(run_requestor_bot())
    elif args.component == "demo":
        asyncio.run(run_demo_scenario())
    else:
        print("Please specify a component to run with --component")
        print("Available components: mediator, ai_news, finance, requestor, demo")