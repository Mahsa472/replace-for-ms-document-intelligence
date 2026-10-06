"""Step 2: Markdown -> structured object, in ONE PydanticAI call.

The whole schema (built from the small classes in schema.py) is passed as a
single `output_type`, so exactly one LLM call fills every field. PydanticAI
validates the model's reply against the schema and retries on validation errors.
"""

from __future__ import annotations

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from brokers import Broker, detect_broker, load_prompt
from schema import ClosingAdvice
from settings import get_settings


def _agent_for(broker: Broker) -> Agent[None, ClosingAdvice]:
    """Build the extraction agent for one broker (model from credentials.env)."""
    s = get_settings()
    client = AsyncOpenAI(api_key=s.llm_api_key.get_secret_value(), base_url=s.llm_base_url)
    model = OpenAIChatModel(s.llm_model, provider=OpenAIProvider(openai_client=client))
    return Agent(
        model,
        output_type=ClosingAdvice,
        system_prompt=load_prompt(broker),
    )


def extract(markdown_text: str) -> tuple[ClosingAdvice, dict]:
    """Detect the broker, run extraction, and return output plus token usage."""
    broker = detect_broker(markdown_text)
    result = _agent_for(broker).run_sync(markdown_text)
    u = result.usage() if callable(result.usage) else result.usage
    return result.output, {
        "input_tokens": u.input_tokens,
        "cached_tokens": u.cache_read_tokens,
        "output_tokens": u.output_tokens,
        "total_tokens": u.total_tokens,
    }
