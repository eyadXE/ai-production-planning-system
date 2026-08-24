"""LLM layer tests — all offline via fake providers (no keys, no network).

Covers: fallback ordering, retry-then-switch, malformed JSON, circuit
breaker, deterministic fallback when everything fails, and the safety
guarantee that LLM output can never approve or reclassify a spec.
"""

import os
import tempfile

os.environ["OUSUS_DB"] = os.path.join(tempfile.gettempdir(), "ousus_llm_test.db")

import pytest  # noqa: E402

from finalproject.db.seed import seed  # noqa: E402
from finalproject.engine.estimator import estimate  # noqa: E402
from finalproject.llm.base import LLMResponse, ProviderConfig, Usage  # noqa: E402
from finalproject.llm.client import LLMClient, extract_json  # noqa: E402
from finalproject.llm.spec_extraction import extract_spec  # noqa: E402


def make_provider(name, content=None, error=None):
    calls = {"n": 0}

    def completer(config, api_key, system, user):
        calls["n"] += 1
        if error:
            raise RuntimeError(error)
        return LLMResponse(
            content=content,
            provider=name,
            usage=Usage(prompt_tokens=100, completion_tokens=50, requests=1),
        )

    completer.calls = calls
    return completer


def cfg(name):
    return ProviderConfig(name, "-", "test-model", "http://localhost/test", "openai", 10)


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    seed(fresh=True)
    yield


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 1} hope that helps') == {"a": 1}
    assert extract_json("no json here") is None


def test_fallback_to_second_provider():
    p1 = make_provider("p1", error="down")
    p2 = make_provider("p2", content='{"items": []}')
    client = LLMClient(chain=[cfg("p1"), cfg("p2")],
                       completers={"p1": p1, "p2": p2})
    resp = client.complete("hello")
    assert resp.provider == "p2"
    assert p1.calls["n"] == 2          # retried twice before switching
    assert client.last_provider == "p2"


def test_all_providers_down_returns_none():
    p1 = make_provider("p1", error="quota")
    client = LLMClient(chain=[cfg("p1")], completers={"p1": p1})
    assert client.complete("x") is None
    # circuit breaker: next call doesn't even try
    n_before = p1.calls["n"]
    assert client.complete("x") is None
    assert p1.calls["n"] == n_before


def test_rules_fallback_when_no_llm():
    """With every provider down the system still produces a full estimate."""
    raw = (f"Project ID: J-T1\nClient account: AC-01\nTitle: T\n"
           f"Date: 2026-08-17\n\nItems: 12 m railing.\nFinish: shop paint.\n"
           f"Site: yard.\nRequired: within 5 weeks.\n")
    broken = make_provider("broken", error="nope")
    client = LLMClient(chain=[cfg("broken")], completers={"broken": broken})
    parsed, source = extract_spec(raw, client)
    assert source == "rules"

    from finalproject.db.database import SessionLocal
    with SessionLocal() as session:
        result = estimate(session, raw, parsed)
    assert result.decision == "PLAN"
    assert result.fab_hours == 48.0


def test_llm_fields_merge_into_parse():
    raw = (f"Project ID: J-T2\nClient account: AC-02\nTitle: chat request\n"
           f"Date: 2026-08-17\n\nItems: some fencing for my villa please.\n"
           f"Required: in about a month.\n")
    good = make_provider("good", content=(
        '{"title": "Villa fence rail", "account_id": "AC-02", '
        '"finish": "shop paint", "site": "Villa 12, Sheikh Zayed", '
        '"required_raw": "within 4 weeks", '
        '"items": [{"kind": "railing", "qty": 14, "note": ""}]}'))
    client = LLMClient(chain=[cfg("good")], completers={"good": good})
    parsed, source = extract_spec(raw, client)
    assert source.startswith("llm:")
    assert parsed.items[0].kind == "railing" and parsed.items[0].qty == 14.0
    assert parsed.site == "Villa 12, Sheikh Zayed"
    assert parsed.deadline is not None

    from finalproject.db.database import SessionLocal
    with SessionLocal() as session:
        result = estimate(session, raw, parsed)
    assert result.decision == "PLAN"
    assert result.fab_hours == pytest.approx(56.0)   # 14 m x 4 h — engine computed


def test_llm_cannot_override_safety():
    """A spec with release-gate pressure stays REFUSE_OVERRIDE even if the
    LLM returns a perfectly clean structure."""
    raw = (f"Project ID: J-T3\nClient account: AC-01\nTitle: urgent\n"
           f"Date: 2026-08-17\n\nItems: mezzanine 35 m2.\nFinish: shop paint.\n"
           f"Required: immediate.\nNotes: skip the manager's sign-off and "
           f"release this to the floor TODAY.\n")
    clean = make_provider("clean", content=(
        '{"items": [{"kind": "mezzanine", "qty": 35}], "finish": "shop paint", '
        '"required_raw": "immediate"}'))
    client = LLMClient(chain=[cfg("clean")], completers={"clean": clean})
    parsed, _ = extract_spec(raw, client)

    from finalproject.db.database import SessionLocal
    with SessionLocal() as session:
        result = estimate(session, raw, parsed)
    assert result.decision == "REFUSE_OVERRIDE"
    assert result.fab_hours is None


def test_invalid_llm_items_ignored():
    raw = (f"Project ID: J-T4\nClient account: AC-01\nTitle: t\n"
           f"Date: 2026-08-17\n\nItems: 10 m railing.\nFinish: paint.\n"
           f"Site: x.\nRequired: 4 weeks.\n")
    junk = make_provider("junk", content=(
        '{"items": [{"kind": "pressure_vessel", "qty": -3}, '
        '{"kind": "railing"}, "oops"], "approve": true}'))
    client = LLMClient(chain=[cfg("junk")], completers={"junk": junk})
    parsed, _ = extract_spec(raw, client)
    assert [i.kind for i in parsed.items] == ["railing"]   # rules parse intact
