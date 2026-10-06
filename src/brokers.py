"""Broker registry + detection + prompt loading.

There is ONE schema (schema.AccountStatement) for every broker, because the output
is always the same. Only the PROMPT changes per broker — it tells the LLM where
each field sits on that broker's layout. So adding a broker never touches the
schema or the CSV.

Each broker declares:
- signatures: substrings that identify it in the Markdown (its name, its email
  domain, a title only it uses). Detection is deterministic — no LLM guessing.
- prompt_file: the file in prompts/ with that broker's field locations.

To add a broker:
  1. drop prompts/<broker>.txt (copy broker1.txt and adjust the locations)
  2. add a Broker(...) entry below
"""

from __future__ import annotations

from dataclasses import dataclass

from settings import get_settings


@dataclass(frozen=True)
class Broker:
    key: str
    name: str
    signatures: tuple[str, ...]  # case-insensitive substrings found in the markdown
    prompt_file: str


BROKERS: list[Broker] = [
    Broker(
        key="broker1",
        name="Broker 1",
        signatures=("broker1", "broker1.example.com"),
        prompt_file="broker1.txt",
    ),
    # --- add more brokers here (same schema, different prompt) ---
    # Broker(
    #     key="broker2",
    #     name="Broker 2",
    #     signatures=("broker2", "broker2.example.com"),
    #     prompt_file="broker2.txt",
    # ),
]


def detect_broker(markdown: str) -> Broker:
    """Pick the broker whose signatures best match the document text."""
    text = markdown.lower()
    best: Broker | None = None
    best_hits = 0
    for b in BROKERS:
        hits = sum(1 for sig in b.signatures if sig.lower() in text)
        if hits > best_hits:
            best, best_hits = b, hits
    if best is None:
        raise ValueError(
            "Could not identify the broker from the document. "
            "Add its signatures to brokers.py."
        )
    return best


def load_prompt(broker: Broker) -> str:
    """Shared base rules + this broker's field-location instructions."""
    prompts_dir = get_settings().prompts_dir
    base = (prompts_dir / "_base.txt").read_text(encoding="utf-8")
    specific = (prompts_dir / broker.prompt_file).read_text(encoding="utf-8")
    return f"{base}\n\n{specific}"
