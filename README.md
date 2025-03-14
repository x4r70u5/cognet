# AI-driven Bot Marketplace

A decentralized network of AI agents (bots) orchestrated by a central intelligent mediation layer that enables autonomous discovery, negotiation, and exchange of services and data.

## Overview

This project implements a marketplace where AI bots can:

- Register their capabilities with a central mediator
- Discover other bots and available services
- Request services from one another
- Negotiate terms of service delivery
- Dynamically create and expose endpoints for data delivery
- Search external resources to fulfill service requests

## Architecture

The marketplace consists of four main components:

1. **Central Mediator**: Registry service for bot registration and service discovery
2. **Requestor Bots**: Bots that request services or data from other bots
3. **Provider Bots**: Bots that fulfill service requests by generating data endpoints
4. **Shared Models**: Data models for service requests, negotiations, and bot information

### Key Features

- **Autonomous Bot Interactions**: Bots can discover and interact without direct human intervention
- **Intelligent Service Matching**: Provider bots use AI to evaluate if they can fulfill requests
- **Dynamic Service Creation**: Bots create temporary endpoints as needed to deliver data
- **Negotiation Protocol**: Simple JSON-based negotiation for request fulfillment
- **Marketplace Registry**: Central coordination point for discovery and logging
- **Direct P2P Communication**: Bots can communicate directly or through the mediator

## Technical Implementation

- Built with Python and FastAPI for clean, async-friendly APIs
- OpenAI integration for intelligent request evaluation and content generation
- Modular design with clear separation of components
- Lightweight JSON-based communication protocol
- In-memory data storage (can be extended to persistent storage)

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
   ```
   pip install fastapi uvicorn httpx openai pydantic
   ```
3. Set your OpenAI API key in the environment:
   ```
   export OPENAI_API_KEY="your-api-key-here"
   ```

### Starting the Components

1. Start the mediator service:
   ```
   python main.py --component mediator
   ```

2. Start provider bots (in separate terminals):
   ```
   python main.py --component ai_news
   python main.py --component finance
   ```

3. Start a requestor bot:
   ```
   python main.py --component requestor
   ```

4. Run the demo scenario (in a separate terminal):
   ```
   python main.py --component demo
   ```

## Demo Scenario

The demo scenario demonstrates two key interactions:

1. **AI Trends Request**: A requestor bot asks for the latest AI trends, and an AI news provider bot responds with structured data about current trends, popularity metrics, and key companies.

2. **Financial Data Request**: A requestor bot asks for specific stock data for Apple (AAPL), and a finance provider bot responds with historical price data.

## Extending the Marketplace

The marketplace can be extended in various ways:

- **Additional Bot Types**: Create specialized bots for different domains
- **Enhanced Negotiation**: Implement more complex negotiation protocols
- **Persistent Storage**: Add database integration for long-term data storage
- **Authentication & Security**: Implement token-based auth between bots
- **Web Dashboard**: Create a visual interface to monitor the marketplace
- **Microservice Deployment**: Containerize bots for scaled deployment

## Project Structure

```
bot-marketplace/
├── main.py              # Entry point and demo scenario
├── mediator.py          # Central registry implementation
├── bot_base.py          # Base class for all bots
├── requestor_bot.py     # Requestor bot implementation
├── provider_bot.py      # Provider bot implementation
├── models.py            # Shared data models
├── config.py            # Configuration settings
└── openai_service.py    # OpenAI client wrapper (provided)
```