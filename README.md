# AI-driven Bot Marketplace

A decentralized network of AI agents (bots) orchestrated by a central intelligent mediation layer that enables autonomous discovery, negotiation, and exchange of services and data.

## Overview

This project implements a marketplace where AI bots can:

- Register their capabilities with a central mediator
- Discover other bots and available services
- Request services from one another through intelligent routing
- Negotiate terms of service delivery
- Dynamically create and expose endpoints for data delivery
- Search external resources to fulfill service requests
- Intelligently enhance and route requests to suitable providers

## Architecture

The marketplace consists of five main components:

1. **Central Mediator**: Registry service for bot registration and service discovery
2. **AI Orchestrator**: Intelligent layer that enhances requests and routes them to suitable providers
3. **Requestor Bots**: Bots that request services or data from other bots
4. **Provider Bots**: Bots that fulfill service requests by generating data endpoints
5. **Shared Models**: Data models for service requests, negotiations, and bot information

### Key Features

- **Autonomous Bot Interactions**: Bots can discover and interact without direct human intervention
- **Smart Request Enhancement**: The AI Orchestrator enhances service requests with additional details
- **Intelligent Provider Matching**: Orchestrator routes requests to the most suitable providers
- **Dynamic Service Creation**: Bots create temporary endpoints as needed to deliver data
- **Service Reuse**: Smart service management prevents duplicate service creation
- **Response Quality Ranking**: Orchestrator evaluates and ranks responses based on quality
- **Negotiation Protocol**: Simple JSON-based negotiation for request fulfillment
- **Marketplace Registry**: Central coordination point for discovery and logging
- **Direct P2P Communication**: Bots can communicate directly or through the mediator

## Technical Implementation

- Built with Python and FastAPI for clean, async-friendly APIs
- OpenAI integration for intelligent request evaluation, enhancement, and content generation
- Modular design with clear separation of components
- Lightweight JSON-based communication protocol
- In-memory data storage (can be extended to persistent storage)
- Hash-based service identification for efficient service reuse

## Running the Application

### Prerequisites

- Python 3.8+
- FastAPI
- Uvicorn
- httpx
- OpenAI Python client

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install fastapi uvicorn httpx openai pydantic
   ```
3. Set your OpenAI API key in config.py:
   ```python
   class Config:
       OPENAI_API_KEY = "your-api-key-here"
   ```

### Starting the Components

Start the mediator service:
```bash
python main.py --component mediator
```

Start the AI Orchestrator (optional, for smart routing):
```bash
python main.py --component orchestrator
```

Start provider bots (in separate terminals):
```bash
python main.py --component ai_news
python main.py --component finance
```

Start a requestor bot:
```bash
python main.py --component requestor
```

Run the standard demo scenario:
```bash
python main.py --component demo
```

Or run the smart demo with AI Orchestrator:
```bash
python main.py --component smart_demo
```

## Demo Scenarios

### Standard Demo
The standard demo demonstrates two key interactions directly between requestors and providers:

- **AI Trends Request**: A requestor bot asks for the latest AI trends, and an AI news provider bot responds with structured data about current trends, popularity metrics, and key companies.
- **Financial Data Request**: A requestor bot asks for specific stock data for Apple (AAPL), and a finance provider bot responds with historical price data.

### Smart Demo (with AI Orchestrator)
The smart demo showcases the AI Orchestrator's capabilities:

- **Enhanced AI Trends Request**: The orchestrator enhances the original request with additional details and routes it to the most suitable AI news provider.
- **Enhanced Financial Data Request**: The orchestrator enhances the financial data request and routes it to the most suitable finance provider.
- **Response Ranking**: For multiple provider responses, the orchestrator ranks them based on quality and relevance.

## Extending the Marketplace

The marketplace can be extended in various ways:

- **Additional Bot Types**: Create specialized bots for different domains
- **Enhanced Negotiation**: Implement more complex negotiation protocols
- **Persistent Storage**: Add database integration for long-term data storage
- **Authentication & Security**: Implement token-based auth between bots
- **Web Dashboard**: Create a visual interface to monitor the marketplace
- **Microservice Deployment**: Containerize bots for scaled deployment
- **Extended AI Capabilities**: Enhance the orchestrator with additional AI-powered features

## Project Structure

```
bot-marketplace/
├── main.py              # Entry point and demo scenarios
├── mediator.py          # Central registry implementation
├── ai_orchestrator.py   # AI Orchestrator implementation
├── bot_base.py          # Base class for all bots
├── requestor_bot.py     # Requestor bot implementation
├── provider_bot.py      # Provider bot implementation
├── models.py            # Shared data models
├── config.py            # Configuration settings
└── openai_service.py    # OpenAI client wrapper
```

## Smart Service Management

The provider bots implement intelligent service management:

- **Request Hashing**: Creates unique identifiers for similar requests
- **Service Reuse**: Updates existing services instead of creating duplicates
- **Service TTL**: Automatically cleans up expired services
- **AI Evaluation**: Uses AI to determine if a bot can fulfill a specific request

The AI Orchestrator adds additional intelligence:

- **Request Enhancement**: Makes requests more detailed and specific
- **Provider Selection**: Matches requests with the most suitable providers
- **Response Evaluation**: Rates and ranks provider responses by quality
- **Transparent Proxying**: Maintains backward compatibility with older components