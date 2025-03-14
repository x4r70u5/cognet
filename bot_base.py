import json
import uuid
import httpx
import asyncio
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from fastapi import FastAPI, HTTPException

from models import (
    Bot, ServiceCategory, ServiceDefinition, ServiceRequest,
    NegotiationOffer, NegotiationResponse, ServiceNotification, get_dict
)
from openai_service import OpenAIService


class BotBase(ABC):
    """Base class for all marketplace bots"""

    def __init__(
            self,
            name: str,
            description: str,
            bot_type: str,
            host: str = "localhost",
            port: int = 8000,
            mediator_url: str = "http://localhost:8100"
    ):
        self.app = FastAPI(title=f"{name} API", description=description)
        self.host = host
        self.port = port
        self.mediator_url = mediator_url
        self.openai_service = OpenAIService()

        # Generate a unique ID for this bot
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.type = bot_type
        self.api_endpoint = f"http://{host}:{port}"
        self.capabilities = []

        # In-memory storage
        self.active_requests: Dict[str, ServiceRequest] = {}
        self.active_negotiations: Dict[str, Any] = {}
        self.active_services: Dict[str, ServiceDefinition] = {}

        # Setup API routes
        self.setup_routes()

    def setup_routes(self):
        """Set up API routes for the bot"""

        # Health check
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok", "bot_id": self.id, "name": self.name}

        # Registration route
        @self.app.get("/info")
        async def get_info():
            return self.get_bot_info()

    def get_bot_info(self) -> Bot:
        """Return information about this bot"""
        return Bot(
            id=self.id,
            name=self.name,
            type=self.type,
            description=self.description,
            api_endpoint=self.api_endpoint,
            capabilities=self.capabilities,
            active=True
        )

    async def register_with_mediator(self) -> bool:
        """Register this bot with the mediator service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.mediator_url}/bots/register",
                    json=self.get_bot_info().dict()
                )
                if response.status_code == 200:
                    print(f"Bot {self.name} registered successfully")
                    return True
                else:
                    print(f"Failed to register bot: {response.text}")
                    return False
        except Exception as e:
            print(f"Error registering with mediator: {e}")
            return False

    async def deregister_from_mediator(self) -> bool:
        """Deregister this bot from the mediator service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.mediator_url}/bots/{self.id}"
                )
                if response.status_code == 200:
                    print(f"Bot {self.name} deregistered successfully")
                    return True
                else:
                    print(f"Failed to deregister bot: {response.text}")
                    return False
        except Exception as e:
            print(f"Error deregistering from mediator: {e}")
            return False

    async def discover_bots(self, bot_type: Optional[str] = None) -> List[Bot]:
        """Discover bots registered with the mediator"""
        try:
            params = {}
            if bot_type:
                params["type"] = bot_type

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.mediator_url}/bots",
                    params=params
                )
                if response.status_code == 200:
                    bots = [Bot(**bot) for bot in response.json()]
                    return bots
                else:
                    print(f"Failed to discover bots: {response.text}")
                    return []
        except Exception as e:
            print(f"Error discovering bots: {e}")
            return []

    async def discover_services(self, category: Optional[ServiceCategory] = None) -> List[ServiceDefinition]:
        """Discover services registered with the mediator"""
        try:
            params = {}
            if category:
                params["category"] = category.value

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.mediator_url}/services",
                    params=params
                )
                if response.status_code == 200:
                    services = [ServiceDefinition(**service) for service in response.json()]
                    return services
                else:
                    print(f"Failed to discover services: {response.text}")
                    return []
        except Exception as e:
            print(f"Error discovering services: {e}")
            return []

    async def notify_service(self, notification: ServiceNotification) -> bool:
        """
        Notify the mediator about a new or updated service.

        Includes better error handling and retry logic.
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{self.mediator_url}/services/notify",
                        json=get_dict(notification)
                    )

                    if response.status_code == 200:
                        return True
                    else:
                        print(f"Service notification failed with status code {response.status_code}: {response.text}")

                # If we got here, the request completed but returned an error
                retry_count += 1
                await asyncio.sleep(1)  # Wait a bit before retrying

            except Exception as e:
                print(f"Error sending service notification: {str(e)}")
                retry_count += 1
                await asyncio.sleep(1)  # Wait a bit before retrying

        return False

    @abstractmethod
    async def start(self):
        """Start the bot service"""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the bot service"""
        pass

    async def run_ai_evaluation(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use OpenAI to evaluate text against context
        """
        system_message = """
        You are an AI assistant that helps evaluate whether a bot can fulfill a specific request.
        Based on the bot's capabilities and the request details, determine if there's a match.
        Provide a JSON response with your evaluation.
        """

        prompt = f"""
        Request: {text}

        Context: {json.dumps(context, indent=2)}

        Evaluate if the bot can fulfill this request based on the context.
        Return a JSON with the following fields:
        - can_fulfill: true/false
        - confidence: a number between 0 and 1
        - reasoning: brief explanation of your decision
        """

        try:
            response = self.openai_service.generate_chat_completion(
                prompt=prompt,
                system_message=system_message,
                temperature=0.3
            )

            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response

            # Find JSON in case the model added explanatory text
            if not json_str.startswith('{'):
                json_start = json_str.find('{')
                if json_start >= 0:
                    json_str = json_str[json_start:]

            return json.loads(json_str)
        except Exception as e:
            print(f"Error in AI evaluation: {e}")
            return {
                "can_fulfill": False,
                "confidence": 0,
                "reasoning": "Error processing the evaluation"
            }