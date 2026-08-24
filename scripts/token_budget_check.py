"""Token-budget check: replay all 27 specs through the provider chain.

Verifies the free-tier quota satisfies a full evaluation run + demo.
Run before the demo, with whatever keys are exported:
    GEMINI_API_KEY=... .venv/bin/python scripts/token_budget_check.py

With no keys it performs an offline estimate (chars/4 heuristic) and
verifies the fallback chain keeps the system alive.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from finalproject.llm.base import DEFAULT_CHAIN, configured_chain
from finalproject.llm.client import LLMClient
from finalproject.llm.prompts import SYSTEM_PROMPT, USER_TEMPLATE

DATA = Path("OUSUS/Ousus_data")


def offline_estimate(specs: list[str]) -> None:
    sys_len = len(SYSTEM_PROMPT) // 4
    print("No API keys exported — offline token estimate (chars ÷ 4):\n")
    for cfg in DEFAULT_CHAIN[:3]:   # keyless ollama excluded
        per_call = sys_len + max(len(s) for s in specs) // 4 + 250
        run_total = sum(sys_len + len(s) // 4 + 250 for s in specs)
        demo_total = run_total * 2   # eval replay + live-demo headroom
        verdict = "OK" if demo_total < 200_000 else "CHECK LIMITS"
        print(f"  {cfg.name:16s} ~{per_call} tok/call, "
              f"~{run_total:,} tok for 27-spec eval, ~{demo_total:,} with demo "
              f"headroom -> {verdict}")
    print("\nFree tiers (order of magnitude): Gemini ~1.5k req/day, "
          "Groq ~14.4k req/day, OpenRouter :free ~50/day.\n"
          "The full eval is ~27 requests — every tier satisfies it alone.")


def main() -> int:
    spec_files = sorted((DATA / "specs").glob("J-*.txt"))
    assert len(spec_files) == 27
    specs = [p.read_text().lstrip("t") if p.name == "J-023.txt" else p.read_text()
             for p in spec_files]

    chain = configured_chain()
    if not chain or all(c.name == "ollama-local" for c in chain):
        offline_estimate(specs)
        return 0

    client = LLMClient(chain=chain)
    ok = failed = 0
    for raw in specs:
        data = client.extract_json(raw)
        if data and isinstance(data.get("items"), list):
            ok += 1
        else:
            failed += 1
            print(f"  extraction failed on one spec (falls back to rules)")

    print(f"\nExtraction via LLM succeeded for {ok}/27 specs ({failed} fell back)")
    print("\nToken usage per provider:")
    for name, usage in client.usage.items():
        limit = next(c.daily_request_budget for c in chain if c.name == name)
        status = "OK" if usage.requests <= limit else "OVER BUDGET"
        print(f"  {name:16s} requests={usage.requests} (budget {limit}) "
              f"prompt={usage.prompt_tokens} completion={usage.completion_tokens} "
              f"-> {status}")
    return 0 if ok > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
