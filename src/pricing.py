"""Token prices per model, used to estimate the cost of each LLM call.

Fill in the prices your provider (or proxy) actually charges. Values are USD per
1,000,000 tokens (the unit most providers quote). Unknown models cost 0 so the
pipeline never crashes on a missing entry.

NOTE: if you go through a proxy that tracks spend (e.g. LiteLLM), it computes the
real cost server-side. This table is a convenient client-side estimate; treat the
provider's own numbers as the source of truth for billing.
"""

from __future__ import annotations

# model name (exactly as LLM_MODEL) -> price per 1M tokens.
# "cached_input" is optional; if missing, cached tokens are billed at "input".
MODEL_PRICES: dict[str, dict[str, float]] = {
    # "my-model": {"input": 2.00, "cached_input": 0.20, "output": 8.00},
}

_ZERO = {"input": 0.0, "output": 0.0}


def cost_usd(usage: dict, model: str) -> float:
    """Estimated cost of one call in USD."""
    p = MODEL_PRICES.get(model, _ZERO)
    cached = usage.get("cached_tokens") or 0
    uncached = usage["input_tokens"] - cached
    return (
        uncached * p["input"]
        + cached * p.get("cached_input", p["input"])
        + usage["output_tokens"] * p["output"]
    ) / 1_000_000
