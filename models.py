from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class BotType(str, Enum):
    REQUESTOR = "requestor"
    PROVIDER = "provider"
    HYBRID = "hybrid"


class ServiceCategory(str, Enum):
    NEWS = "news"
    FINANCE = "finance"
    WEATHER = "weather"
    SOCIAL_MEDIA = "social_media"
    AI = "ai"
    OTHER = "other"


class ServiceFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
    HTML = "html"
    CSV = "csv"


class Bot(BaseModel):
    """Bot registration information"""
    id: str
    name: str
    type: BotType
    description: str
    api_endpoint: str
    capabilities: List[ServiceCategory] = []
    active: bool = True


class ServiceDefinition(BaseModel):
    """Definition of a service provided by a bot"""
    id: str
    name: str
    description: str
    provider_id: str
    category: ServiceCategory
    formats: List[ServiceFormat] = [ServiceFormat.JSON]
    endpoint: str
    parameters: Dict[str, Any] = {}
    ttl: Optional[int] = None  # Time to live in seconds, None means permanent


class ServiceRequest(BaseModel):
    """Request for a service from a bot"""
    requestor_id: str
    category: ServiceCategory
    description: str
    required_format: ServiceFormat = ServiceFormat.JSON
    response_schema: Optional[Dict[str, Any]] = None  # Changed from 'schema' to avoid conflict
    parameters: Dict[str, Any] = {}
    ttl: Optional[int] = None  # How long the requestor needs the service


class NegotiationOffer(BaseModel):
    """Negotiation offer between bots"""
    request_id: str
    provider_id: str
    can_fulfill: bool
    proposed_endpoint: Optional[str] = None
    proposed_format: Optional[ServiceFormat] = None
    constraints: Optional[Dict[str, Any]] = None
    ttl: Optional[int] = None


class NegotiationResponse(BaseModel):
    """Response to a negotiation offer"""
    offer_id: str
    accepted: bool
    modifications: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class ServiceNotification(BaseModel):
    """Notification about a new service"""
    service_id: str
    provider_id: str
    requestor_id: Optional[str] = None
    endpoint: str
    category: ServiceCategory
    description: str
    ttl: Optional[int] = None

# Add this helper function to bot_base.py or models.py

def get_dict(model):
    """
    Get dictionary representation of a Pydantic model,
    handling both v1 and v2 Pydantic versions.
    """
    if hasattr(model, "model_dump"):
        # Pydantic v2
        return model.model_dump()
    else:
        # Pydantic v1
        return model.dict()