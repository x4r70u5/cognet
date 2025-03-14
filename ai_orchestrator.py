import json
import asyncio
import uuid
import httpx
from typing import Dict, List, Optional, Any, Tuple
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
import uvicorn
from pydantic import BaseModel

from models import (
    Bot, BotType, ServiceCategory, ServiceDefinition, ServiceRequest,
    NegotiationOffer, NegotiationResponse, ServiceNotification, ServiceFormat,
    get_dict
)
from openai_service import OpenAIService


class AIOrchestrator:
    """AI Orchestrator that adds intelligent routing and enhancement to the bot marketplace"""

    def __init__(
            self,
            host: str = "localhost",
            port: int = 8300,
            mediator_url: str = "http://localhost:8100"
    ):
        self.app = FastAPI(
            title="AI Orchestrator",
            description="Intelligent layer for Bot Marketplace"
        )
        self.host = host
        self.port = port
        self.mediator_url = mediator_url

        # Initialize OpenAI service for AI capabilities
        self.openai_service = OpenAIService()

        # Cache for provider capabilities and past interactions
        self.provider_cache: Dict[str, Bot] = {}
        self.request_history: Dict[str, Dict[str, Any]] = {}
        self.response_quality: Dict[str, Dict[str, float]] = {}  # provider_id -> quality score

        # Setup routes
        self.setup_routes()

    def setup_routes(self):
        """Set up API routes for the AI Orchestrator"""

        # Health check
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok", "service": "ai_orchestrator"}

        # Smart request publishing with targeted routing
        @self.app.post("/requests/publish")
        async def smart_publish_request(
                request: ServiceRequest,
                background_tasks: BackgroundTasks
        ):
            # Enhance the request with AI
            enhanced_request = await self.enhance_request(request)

            # Publish to mediator first
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.mediator_url}/requests/publish",
                    json=get_dict(enhanced_request)
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to publish request to mediator: {response.text}"
                    )

                result = response.json()
                request_id = result["request_id"]

            # Find suitable providers
            suitable_providers = await self.find_suitable_providers(enhanced_request)

            # Store in history
            self.request_history[request_id] = {
                "original_request": get_dict(request),
                "enhanced_request": get_dict(enhanced_request),
                "suitable_providers": [p.id for p in suitable_providers]
            }

            # Smart routing - targeted distribution to suitable providers
            background_tasks.add_task(
                self.distribute_request,
                request_id,
                enhanced_request,
                suitable_providers
            )

            return {
                "request_id": request_id,
                "message": "Request enhanced and distributed to suitable providers",
                "enhanced": get_dict(enhanced_request) != get_dict(request),
                "target_providers": len(suitable_providers)
            }

        # Smart response collection and evaluation
        # Smart response collection and evaluation
        @self.app.get("/requests/{request_id}/responses")
        async def get_enhanced_responses(request_id: str):
            """Get and enhance responses for a specific request"""
            if request_id not in self.request_history:
                raise HTTPException(status_code=404, detail="Request not found")

            # Collect services from the mediator
            async with httpx.AsyncClient() as client:
                request_info = self.request_history[request_id]
                category = request_info["enhanced_request"]["category"]

                # Log for debugging
                print(f"Looking for services with category: {category}")

                response = await client.get(
                    f"{self.mediator_url}/services",
                    params={"category": category}
                )

                if response.status_code != 200:
                    return {"message": "No services found yet"}

                services = response.json()
                print(f"Found {len(services)} services with matching category")

            # Get data from each service
            service_data = []
            for service in services:
                try:
                    print(f"Attempting to get data from service: {service['id']} at {service['endpoint']}")
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(service["endpoint"])
                        if response.status_code == 200:
                            service_data.append({
                                "service_id": service["id"],
                                "provider_id": service["provider_id"],
                                "data": response.json()
                            })
                            print(f"Successfully retrieved data from service {service['id']}")
                except Exception as e:
                    print(f"Error getting data from service {service['id']}: {e}")

            # If we have multiple responses, evaluate and rank them
            if len(service_data) > 1:
                ranked_data = await self.rank_responses(
                    request_info["enhanced_request"],
                    service_data
                )
                return {
                    "request_id": request_id,
                    "responses": ranked_data,
                    "enhanced": True
                }
            else:
                return {
                    "request_id": request_id,
                    "responses": service_data,
                    "enhanced": False
                }

        # Add this after the get_enhanced_responses endpoint
        @self.app.get("/direct-services/{category}")
        async def get_direct_services(category: str):
            """Directly get services for a category bypassing request history"""

            try:
                # Get all services matching the category
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.mediator_url}/services",
                        params={"category": category}
                    )

                    if response.status_code != 200:
                        return {"message": "No services found"}

                    services = response.json()
                    print(f"Found {len(services)} services with category {category}")

                # Get data from each service
                service_data = []
                for service in services:
                    try:
                        print(f"Trying to get data from {service['endpoint']}")
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            response = await client.get(service['endpoint'])
                            if response.status_code == 200:
                                service_data.append({
                                    "service_id": service["id"],
                                    "provider_id": service["provider_id"],
                                    "data": response.json()
                                })
                                print(f"Successfully got data from {service['endpoint']}")
                    except Exception as e:
                        print(f"Error getting data from service: {e}")

                return {
                    "services": service_data
                }
            except Exception as e:
                print(f"Error in direct services: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # Proxy pass-through to mediator (for backward compatibility)
        @self.app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
        async def proxy_to_mediator(request: Request, path: str):
            """Forward any other requests to the mediator"""
            # Extract body if it exists
            body = None
            if request.method in ["POST", "PUT"]:
                body = await request.body()

            url = f"{self.mediator_url}/{path}"

            # Forward the query parameters
            params = dict(request.query_params)

            # Forward request to mediator
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=request.method,
                    url=url,
                    params=params,
                    content=body,
                    headers={"Content-Type": request.headers.get("Content-Type", "application/json")}
                )

                return response.json()

    async def enhance_request(self, request: ServiceRequest) -> ServiceRequest:
        """Use AI to enhance and clarify the request"""
        prompt = f"""
        Analyze and enhance this service request:
        Category: {request.category}
        Description: {request.description}

        Your task is to:
        1. Make the description more specific and detailed without changing the intent
        2. Identify any implicit parameters that should be made explicit

        Do NOT add new requirements or change the fundamental request.
        """

        try:
            response = self.openai_service.generate_structured_content(
                prompt=prompt,
                output_schema={
                    "enhanced_description": {"type": "string"},
                    "additional_parameters": {"type": "object"}
                }
            )

            if "enhanced_description" in response:
                # Extract enhanced description, handling both string and dict formats
                enhanced_description = response.get("enhanced_description", "")

                # If the description is a dict, extract the actual string value
                if isinstance(enhanced_description, dict) and 'value' in enhanced_description:
                    enhanced_description = enhanced_description['value']
                elif isinstance(enhanced_description,
                                dict) and 'type' in enhanced_description and 'value' in enhanced_description:
                    enhanced_description = enhanced_description['value']

                # Make sure we have a string
                if not isinstance(enhanced_description, str):
                    enhanced_description = str(enhanced_description)

                # Get additional parameters, ensuring it's a dictionary
                additional_params = response.get("additional_parameters", {})
                if not isinstance(additional_params, dict):
                    additional_params = {}

                # Create a new request object to avoid modifying the original
                enhanced_request = ServiceRequest(
                    requestor_id=request.requestor_id,
                    category=request.category,
                    description=enhanced_description,
                    required_format=request.required_format,
                    response_schema=request.response_schema,
                    parameters={**request.parameters, **additional_params},
                    ttl=request.ttl
                )

                return enhanced_request
        except Exception as e:
            print(f"Error enhancing request: {e}")

        # Return original if enhancement fails
        return request

    async def refresh_provider_cache(self):
        """Refresh the cache of provider bots"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.mediator_url}/bots?type=provider")
                if response.status_code == 200:
                    providers = response.json()
                    self.provider_cache = {p["id"]: Bot(**p) for p in providers}
        except Exception as e:
            print(f"Error refreshing provider cache: {e}")

    async def find_suitable_providers(self, request: ServiceRequest) -> List[Bot]:
        """Find the most suitable providers for this request"""
        # Refresh provider cache if empty
        if not self.provider_cache:
            await self.refresh_provider_cache()

        # Basic category filtering first
        category_matching_providers = [
            p for p in self.provider_cache.values()
            if request.category in p.capabilities
        ]

        if not category_matching_providers:
            # If no providers match the category, return empty list
            return []

        if len(category_matching_providers) <= 2:
            # If only a few providers match the category, return all of them
            return category_matching_providers

        # For more providers, use AI to find semantically matching ones
        context = {
            "request": {
                "category": request.category.value,
                "description": request.description
            },
            "providers": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "capabilities": [c.value for c in p.capabilities]
                }
                for p in category_matching_providers
            ]
        }

        prompt = """
        Analyze the request and the available provider bots.
        Determine which providers are most capable of fulfilling this specific request 
        based on their descriptions and capabilities.

        Rank providers by their suitability for this request and return only those with
        a confidence score of 0.7 or higher.
        """

        try:
            result = self.openai_service.generate_structured_content(
                prompt=prompt,
                context=context,
                output_schema={
                    "matches": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "provider_id": {"type": "string"},
                                "confidence": {"type": "number"},
                                "reasoning": {"type": "string"}
                            }
                        }
                    }
                }
            )

            # Get high-confidence matches
            matches = result.get("matches", [])
            good_matches = [m for m in matches if m.get("confidence", 0) > 0.7]

            if good_matches:
                # Return the actual provider objects for good matches
                return [
                    p for p in category_matching_providers
                    if any(m.get("provider_id") == p.id for m in good_matches)
                ]
        except Exception as e:
            print(f"Error finding suitable providers: {e}")

        # Fall back to category matches if AI matching fails
        return category_matching_providers

    async def distribute_request(
            self,
            request_id: str,
            request: ServiceRequest,
            providers: List[Bot]
    ):
        """Distribute a request to the selected providers"""
        print(f"Smart distributing request {request_id} to {len(providers)} selected providers")

        # Create a copy of the request with a demo requestor ID
        demo_request = ServiceRequest(
            requestor_id="demo-orchestrator",  # Add demo- prefix to trigger special handling
            category=request.category,
            description=request.description,
            required_format=request.required_format,
            response_schema=request.response_schema,
            parameters=request.parameters,
            ttl=request.ttl
        )

        for provider in providers:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{provider.api_endpoint}/request",
                        json=get_dict(demo_request)  # Send modified request
                    )
                    print(f"Distributed to {provider.name}: {response.status_code}")
            except Exception as e:
                print(f"Error distributing to {provider.name}: {e}")

    async def rank_responses(
            self,
            request: Dict[str, Any],
            responses: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rank and evaluate responses based on quality and relevance"""
        if len(responses) <= 1:
            return responses

        # Prepare context for evaluation
        context = {
            "request": request,
            "responses": [
                {
                    "provider_id": r["provider_id"],
                    "service_id": r["service_id"],
                    "data_sample": str(r["data"])[:500] + "..." if len(str(r["data"])) > 500 else str(r["data"])
                }
                for r in responses
            ]
        }

        prompt = """
        Evaluate the quality and relevance of each response based on how well it fulfills the request.
        Consider factors such as:
        - Completeness of the information
        - Relevance to the specific request
        - Structure and clarity of the data
        - Accuracy and reliability of the information (based on consistency and how specific it is)

        Rank the responses in order of quality and provide a score for each.
        """

        try:
            result = self.openai_service.generate_structured_content(
                prompt=prompt,
                context=context,
                output_schema={
                    "rankings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_id": {"type": "string"},
                                "quality_score": {"type": "number"},
                                "reasoning": {"type": "string"}
                            }
                        }
                    }
                }
            )

            rankings = result.get("rankings", [])

            # Update our quality tracking
            for rank in rankings:
                service_id = rank.get("service_id")
                score = rank.get("quality_score", 0)

                # Find the provider
                provider_id = None
                for response in responses:
                    if response["service_id"] == service_id:
                        provider_id = response["provider_id"]
                        break

                if provider_id:
                    if provider_id not in self.response_quality:
                        self.response_quality[provider_id] = {"count": 0, "total_score": 0}

                    self.response_quality[provider_id]["count"] += 1
                    self.response_quality[provider_id]["total_score"] += score

            # Sort the responses based on rankings
            ranked_responses = []
            for rank in rankings:
                for response in responses:
                    if response["service_id"] == rank.get("service_id"):
                        response["quality_score"] = rank.get("quality_score", 0)
                        response["quality_reasoning"] = rank.get("reasoning", "")
                        ranked_responses.append(response)
                        break

            # Add any responses not in the rankings
            for response in responses:
                if not any(r["service_id"] == response["service_id"] for r in ranked_responses):
                    response["quality_score"] = 0
                    response["quality_reasoning"] = "Not evaluated"
                    ranked_responses.append(response)

            return ranked_responses
        except Exception as e:
            print(f"Error ranking responses: {e}")

        # Return unranked if evaluation fails
        return responses

    async def start(self):
        """Start the AI Orchestrator service"""
        print(f"Starting AI Orchestrator on {self.host}:{self.port}")
        print(f"Connected to mediator at {self.mediator_url}")

        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()


# If this file is run directly, start the orchestrator
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Orchestrator for Bot Marketplace")
    parser.add_argument("--host", default="localhost", help="Host to bind the service to")
    parser.add_argument("--port", type=int, default=8300, help="Port to bind the service to")
    parser.add_argument("--mediator", default="http://localhost:8100", help="URL of the mediator service")

    args = parser.parse_args()

    orchestrator = AIOrchestrator(
        host=args.host,
        port=args.port,
        mediator_url=args.mediator
    )

    asyncio.run(orchestrator.start())