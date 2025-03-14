import json
import uuid
import httpx
import asyncio
import uvicorn
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Body

from models import (
    Bot, BotType, ServiceCategory, ServiceDefinition, ServiceRequest,
    NegotiationOffer, NegotiationResponse, ServiceNotification, ServiceFormat, get_dict
)
from bot_base import BotBase


class RequestorBot(BotBase):
    """Bot that requests services from provider bots"""

    def __init__(
            self,
            name: str,
            description: str,
            host: str = "localhost",
            port: int = 8000,
            mediator_url: str = "http://localhost:8100"
    ):
        super().__init__(
            name=name,
            description=description,
            bot_type=BotType.REQUESTOR,
            host=host,
            port=port,
            mediator_url=mediator_url
        )

        # Track active requests and responses
        self.request_responses: Dict[str, Any] = {}

        # Additional routes specific to requestor bot
        self.setup_requestor_routes()

    def setup_requestor_routes(self):
        """Set up API routes specific to requestor bot"""

        # Create a new service request
        @self.app.post("/request", response_model=Dict[str, Any])
        async def create_request(
                category: ServiceCategory,
                description: str,
                required_format: ServiceFormat = ServiceFormat.JSON,
                schema: Optional[Dict[str, Any]] = None,
                parameters: Optional[Dict[str, Any]] = None,
                broadcast: bool = False,
                ttl: Optional[int] = None,
                background_tasks: BackgroundTasks = None
        ):
            request_id = str(uuid.uuid4())

            request = ServiceRequest(
                requestor_id=self.id,
                category=category,
                description=description,
                required_format=required_format,
                schema=schema,
                parameters=parameters or {},
                ttl=ttl
            )

            self.active_requests[request_id] = request

            # Publish request to mediator
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.mediator_url}/requests/publish",
                    json=get_dict(request)
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to publish request: {response.text}"
                    )

            # If broadcast is enabled, send request to all provider bots
            if broadcast:
                background_tasks.add_task(
                    self.broadcast_request,
                    request_id,
                    request
                )

            return {
                "request_id": request_id,
                "message": "Service request created successfully",
                "broadcast": broadcast
            }

        # Get status of a request
        @self.app.get("/request/{request_id}/status")
        async def get_request_status(request_id: str):
            if request_id not in self.active_requests:
                raise HTTPException(status_code=404, detail="Request not found")

            # Get any responses that have been received
            responses = self.request_responses.get(request_id, [])

            return {
                "request_id": request_id,
                "request": self.active_requests[request_id],
                "status": "active" if responses else "pending",
                "responses": responses
            }

        # Receive service offer from provider bot
        @self.app.post("/offer", response_model=NegotiationResponse)
        async def receive_offer(offer: NegotiationOffer, background_tasks: BackgroundTasks):
            request_id = offer.request_id

            if request_id not in self.active_requests:
                return NegotiationResponse(
                    offer_id=str(uuid.uuid4()),
                    accepted=False,
                    message="Request not found or expired"
                )

            # Evaluate the offer based on the original request
            evaluation = await self.evaluate_offer(offer, self.active_requests[request_id])

            # Record the response
            if request_id not in self.request_responses:
                self.request_responses[request_id] = []

            self.request_responses[request_id].append({
                "provider_id": offer.provider_id,
                "offer": offer,
                "evaluation": evaluation
            })

            response = NegotiationResponse(
                offer_id=str(uuid.uuid4()),
                accepted=evaluation["accepted"],
                modifications=evaluation.get("modifications"),
                message=evaluation.get("message")
            )

            # If offer is accepted, consume the service
            if evaluation["accepted"] and offer.proposed_endpoint:
                background_tasks.add_task(
                    self.consume_service,
                    request_id=request_id,
                    provider_id=offer.provider_id,
                    endpoint=offer.proposed_endpoint
                )

            return response

        # Receive service data
        @self.app.post("/service-data/{request_id}")
        async def receive_service_data(
                request_id: str,
                data: Dict[str, Any] = Body(...)
        ):
            if request_id not in self.active_requests:
                raise HTTPException(status_code=404, detail="Request not found")

            # Store the received data
            if request_id not in self.request_responses:
                self.request_responses[request_id] = []

            self.request_responses[request_id].append({
                "type": "direct_data",
                "data": data
            })

            return {"message": "Service data received successfully"}

    async def broadcast_request(self, request_id: str, request: ServiceRequest):
        """Broadcast a request to all provider bots"""
        print(f"Broadcasting request {request_id} to all provider bots")

        # Get all provider bots from mediator
        provider_bots = await self.discover_bots(bot_type=BotType.PROVIDER)

        for bot in provider_bots:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{bot.api_endpoint}/request",
                        json=get_dict(request)
                    )

                    print(f"Broadcast to {bot.name}: {response.status_code}")
            except Exception as e:
                print(f"Error broadcasting to {bot.name}: {e}")

    async def evaluate_offer(
            self,
            offer: NegotiationOffer,
            original_request: ServiceRequest
    ) -> Dict[str, Any]:
        """Evaluate a service offer against the original request"""

        # Use AI to evaluate if the offer meets our requirements
        evaluation_context = {
            "original_request": get_dict(original_request),
            "offer": get_dict(offer)
        }

        # For simple demo, just accept if the bot says it can fulfill
        if offer.can_fulfill:
            return {
                "accepted": True,
                "message": "Offer accepted"
            }
        else:
            return {
                "accepted": False,
                "message": "Offer rejected - provider cannot fulfill requirements"
            }

        # In a more sophisticated implementation, we would use AI here:
        # evaluation = await self.run_ai_evaluation(
        #     f"Evaluate if this offer fulfills my request for {original_request.description}",
        #     evaluation_context
        # )

        # return {
        #     "accepted": evaluation.get("can_fulfill", False),
        #     "confidence": evaluation.get("confidence", 0),
        #     "message": evaluation.get("reasoning", "")
        # }

    async def consume_service(self, request_id: str, provider_id: str, endpoint: str):
        """Consume a service from a provider bot"""
        print(f"Consuming service from {provider_id} at {endpoint}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint)

                if response.status_code == 200:
                    # Store the received data
                    if request_id not in self.request_responses:
                        self.request_responses[request_id] = []

                    self.request_responses[request_id].append({
                        "type": "service_data",
                        "provider_id": provider_id,
                        "data": response.json()
                    })

                    print(f"Service data consumed successfully from {provider_id}")
                else:
                    print(f"Failed to consume service: {response.text}")
        except Exception as e:
            print(f"Error consuming service: {e}")

    async def create_service_request(
            self,
            category: ServiceCategory,
            description: str,
            required_format: ServiceFormat = ServiceFormat.JSON,
            schema: Optional[Dict[str, Any]] = None,
            parameters: Optional[Dict[str, Any]] = None,
            broadcast: bool = False,
            ttl: Optional[int] = None
    ) -> str:
        """Programmatically create a service request"""

        request_id = str(uuid.uuid4())

        request = ServiceRequest(
            requestor_id=self.id,
            category=category,
            description=description,
            required_format=required_format,
            schema=schema,
            parameters=parameters or {},
            ttl=ttl
        )

        self.active_requests[request_id] = request

        # Publish request to mediator
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.mediator_url}/requests/publish",
                json=get_dict(request)
            )

            if response.status_code != 200:
                print(f"Failed to publish request: {response.text}")
                return None

        # If broadcast is enabled, send request to all provider bots
        if broadcast:
            await self.broadcast_request(request_id, request)

        return request_id

    async def start(self):
        """Start the bot service"""
        # Register with mediator
        await self.register_with_mediator()

        # Start API server
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

    async def stop(self):
        """Stop the bot service"""
        await self.deregister_from_mediator()