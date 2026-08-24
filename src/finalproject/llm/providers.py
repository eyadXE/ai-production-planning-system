"""HTTP provider adapters. All free-tier OpenAI-compatible endpoints + Ollama."""

import httpx

from finalproject.llm.base import LLMResponse, ProviderConfig, Usage

TIMEOUT_S = 30


class ProviderError(Exception):
    pass


def _openai_style(config: ProviderConfig, api_key: str | None,
                  system: str, user: str) -> LLMResponse:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
    }
    if config.json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        resp = httpx.post(config.base_url, json=payload,
                          headers=headers, timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        raise ProviderError(f"{config.name}: {exc}") from exc
    if resp.status_code != 200:
        raise ProviderError(f"{config.name}: HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise ProviderError(f"{config.name}: malformed response") from exc
    usage = Usage(**{
        k: int(data.get("usage", {}).get(k.replace("_", ""), 0) or 0)
        for k in ("prompt_tokens", "completion_tokens", "requests")
    } | {"requests": 1})
    return LLMResponse(content=str(content), provider=config.name, usage=usage)


def complete(config: ProviderConfig, api_key: str | None,
             system: str, user: str) -> LLMResponse:
    if config.kind in ("openai", "ollama"):
        return _openai_style(config, api_key, system, user)
    raise ProviderError(f"{config.name}: unknown kind {config.kind}")
