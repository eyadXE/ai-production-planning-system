"""LLM client: fallback chain + retries + JSON validation + usage metering.

If every provider fails (no keys, no network, quota exhausted) callers get
`None` and fall back to the deterministic parser — the system never goes
down at a demo.
"""

import json
import logging
import os
import re
import time
from typing import Any, Callable

from finalproject.llm.base import LLMResponse, ProviderConfig, Usage, configured_chain
from finalproject.llm.prompts import SYSTEM_PROMPT, USER_TEMPLATE

log = logging.getLogger(__name__)

MAX_ATTEMPTS_PER_PROVIDER = 2
RETRY_BACKOFF_S = 0.15


def extract_json(content: str) -> dict[str, Any] | None:
    """Best-effort JSON recovery from an LLM reply (incl. reasoning models)."""
    text = content.strip()
    # strip reasoning traces (<think>...</think>) that hybrid models emit
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    # try every {...} block, last one first (reasoning usually precedes it)
    starts = [m.start() for m in re.finditer(r"\{", text)]
    for start in reversed(starts):
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        data = json.loads(candidate)
                        return data if isinstance(data, dict) else None
                    except json.JSONDecodeError:
                        break
    return None


class LLMClient:
    def __init__(self, chain: list[ProviderConfig] | None = None,
                 completers: dict[str, Callable] | None = None):
        self.chain = chain if chain is not None else configured_chain()
        self.completers = completers or {}
        self.usage: dict[str, Usage] = {}
        self.disabled_until: dict[str, float] = {}   # circuit breaker
        self.last_provider: str | None = None

    def _api_key(self, config: ProviderConfig) -> str | None:
        return os.environ.get(config.env_key) if config.env_key != "-" else None

    def _record(self, name: str, usage: Usage) -> None:
        acc = self.usage.setdefault(name, Usage())
        acc.prompt_tokens += usage.prompt_tokens
        acc.completion_tokens += usage.completion_tokens
        acc.requests += usage.requests

    def complete(self, user_text: str,
                 system: str = SYSTEM_PROMPT) -> LLMResponse | None:
        """Try the chain in order; returns None when everything fails."""
        for config in self.chain:
            now = time.time()
            if self.disabled_until.get(config.name, 0) > now:
                continue
            budget = self.usage.get(config.name, Usage())
            if budget.requests >= config.daily_request_budget:
                log.warning("%s over daily budget, skipping", config.name)
                continue
            completer = self.completers.get(
                config.name,
                lambda cfg, key, sys_, usr: _default_complete(cfg, key, sys_, usr),
            )
            for attempt in range(MAX_ATTEMPTS_PER_PROVIDER):
                try:
                    resp = completer(config, self._api_key(config), system, user_text)
                    self._record(config.name, resp.usage)
                    self.last_provider = config.name
                    return resp
                except Exception as exc:  # noqa: BLE001 — any failure falls through
                    log.warning("%s attempt %d failed: %s",
                                config.name, attempt + 1, exc)
                    if "429" in str(exc):
                        break  # quota/rate limit: retrying won't help
                    time.sleep(RETRY_BACKOFF_S * (attempt + 1))
            # provider down/quota — skip it for the next 10 minutes
            self.disabled_until[config.name] = time.time() + 600
        return None

    def extract_json(self, raw_text: str) -> dict[str, Any] | None:
        resp = self.complete(USER_TEMPLATE.format(raw_text=raw_text))
        if resp is None:
            return None
        return extract_json(resp.content)


def _default_complete(config: ProviderConfig, api_key: str | None,
                      system: str, user: str) -> LLMResponse:
    from finalproject.llm.providers import complete as http_complete

    return http_complete(config, api_key, system, user)
