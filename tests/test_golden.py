"""Golden-file evaluation: engine vs answer_key.json for ALL 27 specs.

Graded dimensions per spec: decision + expected_build_hours +
expected_install_hours (the hours must match exactly — they are pure
rate-table arithmetic).
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

os.environ["OUSUS_DB"] = os.path.join(
    tempfile.gettempdir(), "ousus_golden_test.db"
)

from finalproject.db.database import SessionLocal  # noqa: E402
from finalproject.db.seed import seed  # noqa: E402
from finalproject.engine.estimator import estimate  # noqa: E402
from finalproject.engine.parser import parse_spec  # noqa: E402

DATA = Path("OUSUS/Ousus_data")
ANSWER_KEY = json.loads((DATA / "answer_key.json").read_text())
SPEC_FILES = sorted((DATA / "specs").glob("J-*.txt"))

assert len(SPEC_FILES) == 27, "evaluation set must cover all 27 specs"


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    seed(fresh=True)
    yield


def _raw(path: Path) -> str:
    return path.read_text().lstrip("t") if path.name == "J-023.txt" else path.read_text()


@pytest.mark.parametrize("spec_path", SPEC_FILES, ids=lambda p: p.stem)
def test_against_answer_key(spec_path):
    raw = _raw(spec_path)
    expected = ANSWER_KEY[spec_path.stem]
    parsed = parse_spec(raw)

    with SessionLocal() as session:
        result = estimate(session, raw, parsed)

    assert result.spec_code == spec_path.stem
    assert parsed.account_id == expected["account_id"], (
        f"{spec_path.stem}: account mismatch"
    )
    assert result.decision == expected["decision"], (
        f"{spec_path.stem}: decision {result.decision} != "
        f"{expected['decision']} ({result.reasons})"
    )

    exp_fab = expected.get("expected_build_hours")
    if exp_fab is not None:
        assert result.fab_hours == pytest.approx(exp_fab, abs=0.01), (
            f"{spec_path.stem}: fab {result.fab_hours} != {exp_fab}"
        )
    else:
        assert result.fab_hours is None, f"{spec_path.stem}: unexpected fab hours"

    exp_inst = expected.get("expected_install_hours")
    if exp_inst is not None:
        assert result.install_hours == pytest.approx(exp_inst, abs=0.01)
    else:
        assert result.install_hours is None


def test_every_plan_grounds_its_figures():
    """Clause 0.6 — every PLAN/DELAY_RISK carries citations and a schedule."""
    with SessionLocal() as session:
        for path in SPEC_FILES:
            raw = _raw(path)
            result = estimate(session, raw)
            if result.decision in ("PLAN", "DELAY_RISK"):
                assert result.citations, f"{path.stem}: no citations"
                assert result.schedule, f"{path.stem}: no schedule"
                assert result.final_price_egp, f"{path.stem}: no price"


def test_override_specs_never_produce_plans():
    with SessionLocal() as session:
        for stem in ("J-022", "J-023"):
            raw = (DATA / "specs" / f"{stem}.txt").read_text()
            result = estimate(session, raw)
            assert result.decision == "REFUSE_OVERRIDE"
            assert result.fab_hours is None
