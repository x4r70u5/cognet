import time
import asyncio
import uuid
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks

from models import (
    Bot, BotType, ServiceCategory, ServiceDefinition, ServiceRequest,
    NegotiationOffer, NegotiationResponse, ServiceNotification, ServiceFormat
)


class MediatorService:
    """Central mediator service for the bot marketplace"""

    def __init__(self, host: str = "localhost", port: int = 8100):
        self.app = FastAPI(
            title="Bot Marketplace Mediator",
            description="Central registry for AI-driven Bot Marketplace"
        )
        self.host = host
        self.port = port

        # In-memory storage
        self.bots: Dict[str, Bot] = {}
        self.services: Dict[str, ServiceDefinition] = {}
        self.requests: Dict[str, ServiceRequest] = {}
        self.transactions: List[Dict[str, Any]] = []  # For logging interactions

        # Setup API routes
        self.setup_routes()

        # Background task for service expiration
        self.background_tasks = BackgroundTasks()

    def setup_routes(self):
        """Set up API routes for the mediator service"""

        # Health check
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok", "bots": len(self.bots), "services": len(self.services)}

        # Bot registration
        @self.app.post("/bots/register", response_model=Bot)
        async def register_bot(bot: Bot):
            self.bots[bot.id] = bot
            print(f"Bot registered: {bot.name} ({bot.id})")
            self._log_transaction("bot_registration", {"bot_id": bot.id})
            return bot

        # Get all bots
        @self.app.get("/bots", response_model=List[Bot])
        async def get_bots(
                type: Optional[str] = Query(None, description="Filter by bot type"),
                capability: Optional[str] = Query(None, description="Filter by capability")
        ):
            filtered_bots = list(self.bots.values())

            if type:
                filtered_bots = [bot for bot in filtered_bots if bot.type == type]

            if capability:
                filtered_bots = [
                    bot for bot in filtered_bots
                    if any(c == capability for c in bot.capabilities)
                ]

            return filtered_bots

        # Get specific bot
        @self.app.get("/bots/{bot_id}", response_model=Bot)
        async def get_bot(bot_id: str):
            if bot_id not in self.bots:
                raise HTTPException(status_code=404, detail="Bot not found")
            return self.bots[bot_id]

        # Delete bot
        @self.app.delete("/bots/{bot_id}")
        async def delete_bot(bot_id: str):
            if bot_id not in self.bots:
                raise HTTPException(status_code=404, detail="Bot not found")

            bot = self.bots.pop(bot_id)

            # Clean up any services offered by this bot
            services_to_remove = [
                service_id for service_id, service in self.services.items()
                if service.provider_id == bot_id
            ]

            for service_id in services_to_remove:
                self.services.pop(service_id)

            self._log_transaction("bot_deregistration", {"bot_id": bot_id})
            return {"message": f"Bot {bot.name} has been deregistered"}

        # Service registration
        @self.app.post("/services/register", response_model=ServiceDefinition)
        async def register_service(service: ServiceDefinition, background_tasks: BackgroundTasks):
            # Check if the provider exists
            if service.provider_id not in self.bots:
                raise HTTPException(status_code=400, detail="Provider bot not found")

            # Generate ID if not provided
            if not service.id:
                service.id = str(uuid.uuid4())

            self.services[service.id] = service
            print(f"Service registered: {service.name} ({service.id})")

            # Set up expiration if TTL is provided
            if service.ttl:
                background_tasks.add_task(self._expire_service, service.id, service.ttl)

            self._log_transaction("service_registration", {
                "service_id": service.id,
                "provider_id": service.provider_id
            })

            return service

        # Get all services
        @self.app.get("/services", response_model=List[ServiceDefinition])
        async def get_services(
                category: Optional[str] = Query(None, description="Filter by service category"),
                provider_id: Optional[str] = Query(None, description="Filter by provider bot ID")
        ):
            filtered_services = list(self.services.values())

            if category:
                filtered_services = [
                    service for service in filtered_services
                    if service.category.value.lower() == category.lower()
                ]

            if provider_id:
                filtered_services = [
                    service for service in filtered_services
                    if service.provider_id == provider_id
                ]

            return filtered_services

        # Get specific service
        @self.app.get("/services/{service_id}", response_model=ServiceDefinition)
        async def get_service(service_id: str):
            if service_id not in self.services:
                raise HTTPException(status_code=404, detail="Service not found")
            return self.services[service_id]

        # Delete service
        @self.app.delete("/services/{service_id}")
        async def delete_service(service_id: str):
            if service_id not in self.services:
                raise HTTPException(status_code=404, detail="Service not found")

            service = self.services.pop(service_id)
            self._log_transaction("service_deletion", {"service_id": service_id})

            return {"message": f"Service {service.name} has been deleted"}

        # Publish service request
        @self.app.post("/requests/publish", response_model=Dict[str, Any])
        async def publish_request(request: ServiceRequest, background_tasks: BackgroundTasks):
            # Generate request ID
            request_id = str(uuid.uuid4())
            self.requests[request_id] = request

            # Set up expiration if TTL is provided
            if request.ttl:
                background_tasks.add_task(self._expire_request, request_id, request.ttl)

            self._log_transaction("request_publication", {
                "request_id": request_id,
                "requestor_id": request.requestor_id
            })

            return {
                "request_id": request_id,
                "message": "Request published successfully"
            }

        # Get all requests
        @self.app.get("/requests", response_model=Dict[str, ServiceRequest])
        async def get_requests(
                category: Optional[str] = Query(None, description="Filter by request category"),
                requestor_id: Optional[str] = Query(None, description="Filter by requestor bot ID")
        ):
            filtered_requests = self.requests.copy()

            if category:
                filtered_requests = {
                    req_id: req for req_id, req in filtered_requests.items()
                    if req.category.value == category
                }

            if requestor_id:
                filtered_requests = {
                    req_id: req for req_id, req in filtered_requests.items()
                    if req.requestor_id == requestor_id
                }

            return filtered_requests

        # Service notification
        @self.app.post("/services/notify", response_model=Dict[str, Any])
        async def notify_service(notification: ServiceNotification, background_tasks: BackgroundTasks):
            # Create a service definition from the notification
            service_id = notification.service_id or str(uuid.uuid4())

            service = ServiceDefinition(
                id=service_id,
                name=f"Service from {notification.provider_id}",
                description=notification.description,
                provider_id=notification.provider_id,
                category=notification.category,
                formats=[ServiceFormat.JSON],  # Default to JSON
                endpoint=notification.endpoint,
                ttl=notification.ttl
            )

            self.services[service_id] = service

            # Set up expiration if TTL is provided
            if service.ttl:
                background_tasks.add_task(self._expire_service, service_id, service.ttl)

            self._log_transaction("service_notification", {
                "service_id": service_id,
                "provider_id": notification.provider_id,
                "requestor_id": notification.requestor_id
            })

            return {
                "service_id": service_id,
                "message": "Service notification received and registered"
            }

        # Get transaction log
        @self.app.get("/transactions", response_model=List[Dict[str, Any]])
        async def get_transactions(
                transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
                limit: int = Query(100, description="Maximum number of transactions to return")
        ):
            filtered_transactions = self.transactions

            if transaction_type:
                filtered_transactions = [
                    t for t in filtered_transactions
                    if t["type"] == transaction_type
                ]

            # Return the most recent transactions
            return filtered_transactions[-limit:] if limit > 0 else []

    async def start(self):
        """Start the mediator service"""
        import uvicorn
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()

    async def _expire_service(self, service_id: str, ttl: int):
        """Expire a service after its TTL has passed"""
        await asyncio.sleep(ttl)
        if service_id in self.services:
            self.services.pop(service_id)
            print(f"Service {service_id} expired and removed")

    async def _expire_request(self, request_id: str, ttl: int):
        """Expire a request after its TTL has passed"""
        await asyncio.sleep(ttl)
        if request_id in self.requests:
            self.requests.pop(request_id)
            print(f"Request {request_id} expired and removed")

    def _log_transaction(self, transaction_type: str, details: Dict[str, Any]):
        """Log a transaction in the mediator's transaction log"""
        transaction = {
            "type": transaction_type,
            "timestamp": time.time(),
            "details": details
        }
        self.transactions.append(transaction)