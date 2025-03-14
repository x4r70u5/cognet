import json
import time
import openai
from config import Config


class OpenAIService:
    """Service for interacting with OpenAI APIs, adapted for Bot Marketplace"""

    def __init__(self):
        """Initialize the OpenAI service with API key from config"""
        self.client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)

        # Token bucket for rate limiting
        self.TOKEN_LIMIT = 30000  # TPM limit
        self.token_bucket = self.TOKEN_LIMIT
        self.last_refill = time.time()

    def _refill_bucket(self):
        """Refill the token bucket based on time passed"""
        now = time.time()
        time_passed = now - self.last_refill
        # Refill rate: full capacity per minute
        tokens_to_add = time_passed * (self.TOKEN_LIMIT / 60)
        self.token_bucket = min(self.TOKEN_LIMIT, self.token_bucket + tokens_to_add)
        self.last_refill = now

    def _consume_tokens(self, tokens):
        """Consume tokens from the bucket if available"""
        self._refill_bucket()
        if self.token_bucket >= tokens:
            self.token_bucket -= tokens
            return True
        return False

    def generate_chat_completion(self, prompt, system_message=None, temperature=0.7):
        """
        Generate a completion using the Chat API

        Args:
            prompt (str): The user prompt
            system_message (str, optional): System message to guide the model
            temperature (float, optional): Creativity parameter (0.0-1.0)

        Returns:
            str: The generated text response
        """
        messages = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": prompt})

        # Estimate tokens for rate limiting
        estimated_tokens = len(prompt) // 4  # Rough estimate: 4 chars ≈ 1 token
        if not self._consume_tokens(estimated_tokens):
            return "Rate limit exceeded. Please try again later."

        try:
            # Use either gpt-4o-mini or gpt-3.5-turbo depending on availability
            model = "gpt-4o-mini"

            # Fallback model if needed
            # If you don't have access to gpt-4o-mini, uncomment the next line
            # model = "gpt-3.5-turbo"

            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error in chat completion: {e}")

            # Try fallback model if the first one fails
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=temperature
                )
                return response.choices[0].message.content
            except Exception as e2:
                print(f"Error with fallback model: {e2}")
                return "An error occurred while generating content."

    def generate_structured_content(self, prompt, context=None, output_schema=None):
        """
        Generate structured content (JSON) using the Chat API

        Args:
            prompt (str): The specific request for content generation
            context (dict, optional): Additional context information
            output_schema (dict, optional): The expected JSON schema structure

        Returns:
            dict: The generated structured content
        """
        # Create the complete prompt with context and schema information
        complete_prompt = prompt

        if context:
            context_str = json.dumps(context, indent=2)
            complete_prompt = f"{complete_prompt}\n\nContext:\n{context_str}"

        if output_schema:
            schema_str = json.dumps(output_schema, indent=2)
            complete_prompt = f"{complete_prompt}\n\nRespond with valid JSON matching this schema:\n{schema_str}"
        else:
            complete_prompt = f"{complete_prompt}\n\nRespond with valid JSON."

        system_message = "You are a creative game content generator. Generate detailed, imaginative, and coherent game content that follows the specified format. Always respond with valid JSON."

        try:
            response_text = self.generate_chat_completion(complete_prompt, system_message, temperature=0.8)

            # Extract JSON from response (handle potential markdown code blocks)
            json_str = response_text
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()

            # Find JSON in case the model added explanatory text
            if not json_str.startswith('{'):
                json_start = json_str.find('{')
                if json_start >= 0:
                    json_str = json_str[json_start:]

            return json.loads(json_str)
        except json.JSONDecodeError:
            print(f"Error decoding JSON from response: {response_text}")
            return {"error": "Failed to generate valid structured content"}
        except Exception as e:
            print(f"Error in structured content generation: {e}")
            return {"error": "An unexpected error occurred"}