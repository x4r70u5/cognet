import json
import uuid
import random
import httpx
import asyncio
import uvicorn
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks

from models import (
    Bot, BotType, ServiceCategory, ServiceDefinition, ServiceRequest,
    NegotiationOffer, NegotiationResponse, ServiceNotification, ServiceFormat, get_dict
)
from bot_base import BotBase


class ProviderBot(BotBase):
    """Bot that provides services to requestor bots"""

    def __init__(
        self,
        name: str,
        description: str,
        capabilities: List[ServiceCategory],
        host: str = "localhost",
        port: int = 8000,
        mediator_url: str = "http://localhost:8100"
    ):
        super().__init__(
            name=name,
            description=description,
            bot_type=BotType.PROVIDER,
            host=host,
            port=port,
            mediator_url=mediator_url
        )

        # Set capabilities
        self.capabilities = capabilities

        # Track dynamic endpoints and data
        self.dynamic_endpoints: Dict[str, Dict[str, Any]] = {}

        # Additional routes specific to provider bot
        self.setup_provider_routes()

        # Poll for requests from the mediator
        self.keep_running = True

    def setup_provider_routes(self):
        """Set up API routes specific to provider bot"""

        # Receive direct request from requestor
        @self.app.post("/request")
        async def receive_request(
                request: ServiceRequest,
                background_tasks: BackgroundTasks
        ):
            # Process the request in the background
            background_tasks.add_task(
                self.process_request,
                request
            )

            return {"message": "Request received and being processed"}

        # Dynamic endpoints for services
        @self.app.get("/services/{service_id}")
        async def get_service_data(service_id: str):
            if service_id not in self.dynamic_endpoints:
                raise HTTPException(status_code=404, detail="Service not found")

            return self.dynamic_endpoints[service_id]["data"]

    async def start(self):
        """Start the bot service"""
        # Register with mediator
        await self.register_with_mediator()

        # Start polling for requests
        asyncio.create_task(self.poll_for_requests())

        # Start service cleanup task
        asyncio.create_task(self.cleanup_expired_services())

        # Start API server
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

    async def stop(self):
        """Stop the bot service"""
        self.keep_running = False
        await self.deregister_from_mediator()

    async def poll_for_requests(self):
        """Poll the mediator for new service requests"""
        print(f"Started polling for requests")

        while self.keep_running:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.mediator_url}/requests"
                    )

                    if response.status_code == 200:
                        requests_dict = response.json()

                        for request_id, request in requests_dict.items():
                            # Skip if we've already processed this request
                            if request_id in self.active_requests:
                                continue

                            # Convert dict to ServiceRequest
                            request_obj = ServiceRequest(**request)

                            # Process the request
                            asyncio.create_task(self.process_request(request_obj, request_id))

            except Exception as e:
                print(f"Error polling for requests: {e}")

            # Wait before polling again
            await asyncio.sleep(5)  # Poll every 5 seconds

    async def process_request(
            self,
            request: ServiceRequest,
            request_id: Optional[str] = None
    ):
        """Process a service request with smart service management"""
        # Skip if we've already processed this
        request_key = request_id or request.requestor_id + request.description
        if request_key in self.active_requests:
            return

        self.active_requests[request_key] = request

        # Evaluate if we can fulfill this request based on our capabilities
        can_fulfill = request.category in self.capabilities

        # If we can't fulfill the basic category, no need to go further
        if not can_fulfill:
            print(f"Cannot fulfill request: {request.category} not in capabilities")
            return

        # For a more sophisticated approach, use AI to evaluate semantic similarity
        context = {
            "bot_capabilities": [c.value for c in self.capabilities],
            "bot_description": self.description,
            "request": {
                "category": request.category.value,
                "description": request.description
            }
        }

        evaluation = await self.run_ai_evaluation(
            request.description,
            context
        )

        print(f"AI evaluation: {evaluation}")

        # Special handling for demo-orchestrator requests - TOGGLE THIS SECTION ON/OFF
        # ======================================================================
        if request.requestor_id == "demo-orchestrator" and request.category in self.capabilities:
            print(f"Orchestrator request detected. Overriding evaluation for testing purposes.")
            # Force acceptance for orchestrator requests in our capabilities
            evaluation = {"can_fulfill": True, "confidence": 0.8,
                          "reasoning": "Accepting orchestrator request for testing"}
        # ======================================================================

        # If we can fulfill the request, check for existing services or create a new one
        if evaluation.get("can_fulfill", False):
            # Create a request hash to identify similar requests
            request_hash = self._create_request_hash(request)

            # Check for existing services that match this request
            existing_service = await self._find_matching_service(request, request_hash)

            if existing_service:
                print(f"Found existing service that matches this request: {existing_service['endpoint']}")

                # Update the existing service with fresh data
                service_id = existing_service['id']
                endpoint = existing_service['endpoint']

                # Generate fresh data
                data = await self.generate_data(request)

                # Update the dynamic endpoint
                self.dynamic_endpoints[service_id] = {
                    "request": request,
                    "data": data,
                    "created_at": asyncio.get_event_loop().time(),
                    "hash": request_hash
                }

                print(f"Updated existing service at endpoint: {endpoint}")

                # Notify mediator about the updated service
                notification = ServiceNotification(
                    service_id=service_id,
                    provider_id=self.id,
                    requestor_id=request.requestor_id,
                    endpoint=endpoint,
                    category=request.category,
                    description=f"Service for: {request.description} (Updated)",
                    ttl=3600  # 1 hour TTL by default
                )

                success = await self.notify_service(notification)
                if success:
                    print(f"Service update registered with mediator at endpoint: {endpoint}")
                else:
                    print("Failed to register service update with mediator")

                return

            # If no existing service found, create a new one
            # Generate an offer
            offer = NegotiationOffer(
                request_id=request_key,
                provider_id=self.id,
                can_fulfill=True,
                proposed_format=request.required_format,
                ttl=3600  # 1 hour TTL by default
            )

            # Create a dynamic endpoint for this request
            service_id = str(uuid.uuid4())
            endpoint = f"{self.api_endpoint}/services/{service_id}"
            offer.proposed_endpoint = endpoint

            # Generate data for the request
            data = await self.generate_data(request)

            # Store the data for the dynamic endpoint with the request hash
            self.dynamic_endpoints[service_id] = {
                "request": request,
                "data": data,
                "created_at": asyncio.get_event_loop().time(),
                "hash": request_hash
            }

            # For demo requestors, skip negotiation and directly register the service
            is_demo_requestor = request.requestor_id.startswith("demo-")

            if is_demo_requestor:
                print(f"Demo requestor detected. Skipping negotiation and directly registering service.")

                # Notify mediator about the new service
                notification = ServiceNotification(
                    service_id=service_id,
                    provider_id=self.id,
                    requestor_id=request.requestor_id,
                    endpoint=endpoint,
                    category=request.category,
                    description=f"Service for: {request.description}",
                    ttl=3600  # 1 hour TTL by default
                )

                success = await self.notify_service(notification)
                if success:
                    print(f"Service registered with mediator at endpoint: {endpoint}")
                else:
                    print("Failed to register service with mediator")

                return

            # For real requestors, try negotiation
            try:
                requestor_bot = await self.get_bot_info_by_id(request.requestor_id)

                if requestor_bot:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{requestor_bot.api_endpoint}/offer",
                            json=get_dict(offer)
                        )

                        if response.status_code == 200:
                            # Parse the response
                            offer_response = NegotiationResponse(**response.json())

                            # If offer accepted, fulfill the request
                            if offer_response.accepted:
                                await self.fulfill_request(
                                    request,
                                    service_id,
                                    endpoint
                                )
                else:
                    print(f"Requestor bot {request.requestor_id} not found. Cannot negotiate.")

                    # Even if requestor not found, register the service with the mediator
                    notification = ServiceNotification(
                        service_id=service_id,
                        provider_id=self.id,
                        requestor_id=request.requestor_id,
                        endpoint=endpoint,
                        category=request.category,
                        description=f"Service for: {request.description}",
                        ttl=3600  # 1 hour TTL by default
                    )

                    success = await self.notify_service(notification)
                    if success:
                        print(f"Service registered with mediator at endpoint: {endpoint}")
                    else:
                        print("Failed to register service with mediator")

            except Exception as e:
                print(f"Error in negotiation: {e}")

                # Register the service anyway in case of error
                notification = ServiceNotification(
                    service_id=service_id,
                    provider_id=self.id,
                    requestor_id=request.requestor_id,
                    endpoint=endpoint,
                    category=request.category,
                    description=f"Service for: {request.description}",
                    ttl=3600  # 1 hour TTL by default
                )

                success = await self.notify_service(notification)
                if success:
                    print(f"Service registered with mediator despite error at endpoint: {endpoint}")
                else:
                    print("Failed to register service with mediator")

    async def get_bot_info_by_id(self, bot_id: str) -> Optional[Bot]:
        """Get bot information from the mediator"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.mediator_url}/bots/{bot_id}"
                )

                if response.status_code == 200:
                    return Bot(**response.json())
                else:
                    print(f"Failed to get bot info: {response.text}")
                    return None
        except Exception as e:
            print(f"Error getting bot info: {e}")
            return None

    async def fulfill_request(
            self,
            request: ServiceRequest,
            service_id: str,
            endpoint: str
    ):
        """Fulfill a service request by generating data and exposing it at an endpoint"""
        print(f"Fulfilling request: {request.description}")

        # Generate data based on the request
        data = await self.generate_data(request)

        # Store the data for the dynamic endpoint
        self.dynamic_endpoints[service_id] = {
            "request": request,
            "data": data,
            "created_at": asyncio.get_event_loop().time()
        }

        # Notify mediator about the new service
        notification = ServiceNotification(
            service_id=service_id,
            provider_id=self.id,
            requestor_id=request.requestor_id,
            endpoint=endpoint,
            category=request.category,
            description=f"Service for: {request.description}",
            ttl=3600  # 1 hour TTL by default
        )

        await self.notify_service(notification)

        print(f"Service created at endpoint: {endpoint}")

        # Also send the data directly to the requestor
        try:
            requestor_bot = await self.get_bot_info_by_id(request.requestor_id)

            if requestor_bot:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{requestor_bot.api_endpoint}/service-data/{service_id}",
                        json=data
                    )

                    if response.status_code == 200:
                        print(f"Data sent directly to requestor")
        except Exception as e:
            print(f"Error sending data directly: {e}")

    async def generate_data(self, request: ServiceRequest) -> Dict[str, Any]:
        """Generate data based on the request"""

        # Example for AI trends
        if request.category == ServiceCategory.AI:
            # In a real implementation, we would search external APIs or use web scraping
            # For demo purposes, we'll generate synthetic data

            # Create prompt for OpenAI to generate AI trends data
            prompt = f"""
            Generate current AI trends data in JSON format with the following fields:
            - trend_name: Name of the AI trend
            - description: Short description of the trend
            - popularity: Number from 1-100 indicating popularity
            - category: One of [LLM, Computer Vision, Robotics, ML Ops, Other]
            - key_companies: List of companies involved in this trend

            The request was for: {request.description}
            Return only the JSON data without any explanation.
            """

            # Generate data using OpenAI
            try:
                response = self.openai_service.generate_structured_content(
                    prompt=prompt,
                    output_schema={
                        "type": "object",
                        "properties": {
                            "trends": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "trend_name": {"type": "string"},
                                        "description": {"type": "string"},
                                        "popularity": {"type": "number"},
                                        "category": {"type": "string"},
                                        "key_companies": {"type": "array", "items": {"type": "string"}}
                                    }
                                }
                            },
                            "last_updated": {"type": "string"},
                            "source": {"type": "string"}
                        }
                    }
                )

                return response
            except Exception as e:
                print(f"Error generating AI data: {e}")
                # Fallback to dummy data
                return self._generate_dummy_ai_trends()

        # Example for financial data
        elif request.category == ServiceCategory.FINANCE:
            # Create dummy financial data
            return self._generate_dummy_financial_data(request)

        # For other categories, generate generic data
        else:
            return {
                "message": f"Data for {request.category.value}",
                "description": request.description,
                "timestamp": asyncio.get_event_loop().time(),
                "provider": self.name,
                "data": {
                    "sample": "This is sample data",
                    "values": [random.randint(1, 100) for _ in range(5)]
                }
            }

    def _generate_dummy_ai_trends(self) -> Dict[str, Any]:
        """Generate dummy AI trends data"""
        return {
            "trends": [
                {
                    "trend_name": "Multimodal LLMs",
                    "description": "Language models that can process multiple types of data including text, images, and audio",
                    "popularity": 95,
                    "category": "LLM",
                    "key_companies": ["OpenAI", "Anthropic", "Google", "Meta"]
                },
                {
                    "trend_name": "AI Agents",
                    "description": "Autonomous AI systems that can perform tasks without human intervention",
                    "popularity": 88,
                    "category": "LLM",
                    "key_companies": ["Anthropic", "OpenAI", "Google DeepMind"]
                },
                {
                    "trend_name": "Generative Video Models",
                    "description": "AI models that can generate high-quality video from text prompts",
                    "popularity": 82,
                    "category": "Computer Vision",
                    "key_companies": ["Runway", "OpenAI", "Stability AI"]
                },
                {
                    "trend_name": "On-Device AI",
                    "description": "Running AI models locally on mobile devices and laptops",
                    "popularity": 79,
                    "category": "ML Ops",
                    "key_companies": ["Apple", "Google", "Qualcomm", "Samsung"]
                },
                {
                    "trend_name": "Synthetic Data Generation",
                    "description": "Creating artificial datasets for training AI models",
                    "popularity": 76,
                    "category": "ML Ops",
                    "key_companies": ["Mostly AI", "Synthesis AI", "Gretel"]
                }
            ],
            "last_updated": "2025-03-14",
            "source": "AI Bot Marketplace Demo"
        }

    def _generate_dummy_financial_data(self, request: ServiceRequest) -> Dict[str, Any]:
        """Generate dummy financial data"""
        # Check if the request is for stock data
        if "stock" in request.description.lower():
            stock_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
            selected_symbol = random.choice(stock_symbols)

            if any(symbol.lower() in request.description.lower() for symbol in stock_symbols):
                for symbol in stock_symbols:
                    if symbol.lower() in request.description.lower():
                        selected_symbol = symbol
                        break

            # Generate daily stock data for the last quarter (90 days)
            base_price = random.uniform(100, 500)
            daily_data = []

            for day in range(90):
                date = f"2025-{(3 - day // 30):02d}-{(30 - day % 30):02d}"
                price_change = random.uniform(-0.05, 0.05)  # -5% to +5%
                open_price = base_price * (1 + price_change)
                close_price = open_price * (1 + random.uniform(-0.02, 0.02))
                high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.01))
                low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.01))
                volume = int(random.uniform(1000000, 10000000))

                daily_data.append({
                    "date": date,
                    "open": round(open_price, 2),
                    "high": round(high_price, 2),
                    "low": round(low_price, 2),
                    "close": round(close_price, 2),
                    "volume": volume
                })

                base_price = close_price

            return {
                "symbol": selected_symbol,
                "name": {
                    "AAPL": "Apple Inc.",
                    "MSFT": "Microsoft Corporation",
                    "GOOGL": "Alphabet Inc.",
                    "AMZN": "Amazon.com, Inc.",
                    "META": "Meta Platforms, Inc."
                }[selected_symbol],
                "period": "Last Quarter",
                "data": daily_data,
                "last_updated": "2025-03-14"
            }
        else:
            # Generate market indices
            return {
                "market_summary": {
                    "indices": [
                        {"name": "S&P 500", "value": 5824.15, "change": 0.67},
                        {"name": "Dow Jones", "value": 41283.45, "change": 0.43},
                        {"name": "NASDAQ", "value": 18765.32, "change": 0.91},
                        {"name": "Russell 2000", "value": 2345.67, "change": -0.21}
                    ],
                    "sectors": [
                        {"name": "Technology", "change": 1.23},
                        {"name": "Healthcare", "change": 0.54},
                        {"name": "Financial", "change": -0.32},
                        {"name": "Energy", "change": 0.87},
                        {"name": "Consumer Cyclical", "change": 0.12}
                    ]
                },
                "last_updated": "2025-03-14"
            }


    def _create_request_hash(self, request: ServiceRequest) -> str:
        """
        Create a hash of the request to identify similar requests.

        This function generates a hash based on the category and key elements
        of the description, ignoring minor variations.
        """
        import hashlib
        import re

        # Normalize the description by removing punctuation, extra spaces,
        # and converting to lowercase
        normalized_description = re.sub(r'[^\w\s]', '', request.description.lower())
        normalized_description = re.sub(r'\s+', ' ', normalized_description).strip()

        # For financial requests, extract key information like stock symbol
        if request.category == ServiceCategory.FINANCE:
            # Extract stock symbol if present
            stock_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
            for symbol in stock_symbols:
                if symbol.lower() in normalized_description.lower():
                    normalized_description = f"{symbol} stock data"
                    break

        # For AI requests, simplify to core request
        if request.category == ServiceCategory.AI:
            if "trends" in normalized_description.lower():
                normalized_description = "ai trends"

        # Create a hash of the category and normalized description
        hash_input = f"{request.category.value}:{normalized_description}"
        return hashlib.md5(hash_input.encode()).hexdigest()


    async def _find_matching_service(self, request: ServiceRequest, request_hash: str) -> Optional[Dict[str, Any]]:
        """
        Find an existing service that matches the request.

        Checks both local dynamic endpoints and mediator services.
        """
        # First check our own dynamic endpoints
        for service_id, service_data in self.dynamic_endpoints.items():
            if service_data.get("hash") == request_hash:
                # Found a matching service in our local endpoints
                return {
                    "id": service_id,
                    "endpoint": f"{self.api_endpoint}/services/{service_id}"
                }

        # If not found locally, check the mediator's services
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.mediator_url}/services",
                    params={"category": request.category.value, "provider_id": self.id}
                )

                if response.status_code == 200:
                    services = response.json()

                    # Look for matching services in the response
                    for service in services:
                        # Get the service data to check its hash
                        try:
                            service_response = await client.get(service["endpoint"])
                            if service_response.status_code == 200:
                                # The service exists and is accessible
                                return service
                        except Exception:
                            # This service might be unreachable, skip it
                            continue

        except Exception as e:
            print(f"Error checking mediator services: {e}")

        # No matching service found
        return None


    async def cleanup_expired_services(self):
        """
        Periodically clean up expired services.

        This method runs as a background task to remove services
        that have exceeded their TTL.
        """
        while self.keep_running:
            current_time = asyncio.get_event_loop().time()

            # Check local dynamic endpoints
            expired_service_ids = []
            for service_id, service_data in self.dynamic_endpoints.items():
                created_at = service_data.get("created_at", 0)
                ttl = 3600  # Default 1 hour TTL

                if current_time - created_at > ttl:
                    expired_service_ids.append(service_id)

            # Remove expired services from local storage
            for service_id in expired_service_ids:
                self.dynamic_endpoints.pop(service_id, None)
                print(f"Removed expired local service: {service_id}")

            # Sleep for a while before checking again
            await asyncio.sleep(300)  # Check every 5 minutes