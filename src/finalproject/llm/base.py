"""Provider protocol + registry.

Golden rule: the LLM layer is used ONLY for text -> structure extraction.
All safety classification and every number stays in the deterministic
engine; engine code never imports this package.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    requests: int = 0


@dataclass
class ProviderConfig:
    name: str
    env_key: str            # env var holding the API key ("-" = none needed)
    model: str
    base_url: str
    kind: str               # gemini | openai | ollama
    daily_request_budget: int = 1400   # conservative free-tier headroom
    json_mode: bool = True  # some models choke on response_format=json_object


DEFAULT_CHAIN = [
    ProviderConfig(
        "gemini", "GEMINI_API_KEY", "gemini-2.5-flash",
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "openai", 1400,
    ),
    ProviderConfig(
        "groq", "GROQ_API_KEY", "openai/gpt-oss-120b",
        "https://api.groq.com/openai/v1/chat/completions",
        "openai", 700, json_mode=False,
    ),
    ProviderConfig(
        "openrouter-free", "OPENROUTER_API_KEY",
        "nvidia/nemotron-3.5-lightning:free",
        "https://openrouter.ai/api/v1/chat/completions",
        "openai", 200,
    ),
    ProviderConfig(
        "ollama-local", "-", os.environ.get("OUSUS_OLLAMA_MODEL", "llama3.2"),
        os.environ.get("OUSUS_OLLAMA_URL", "http://localhost:11434/v1/chat/completions"),
        "ollama", 100000,
    ),
]


def configured_chain() -> list[ProviderConfig]:
    """Providers with credentials present (or keyless), in fallback order."""
    chain = []
    for p in DEFAULT_CHAIN:
        if p.env_key == "-":
            chain.append(p)
            continue
        if os.environ.get(p.env_key):
            chain.append(p)
    return chain


@dataclass
class LLMResponse:
    content: str
    provider: str
    usage: Usage = field(default_factory=Usage)
