from __future__ import annotations

import asyncio
from pathlib import Path

from sentinel_core.validation_harness import validate_builtin_plugins

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins"


def test_offline_harness_replays_plugins_and_validates_candidate_review() -> None:
    results = asyncio.run(validate_builtin_plugins(PLUGIN_ROOT))

    assert {result.plugin_id for result in results} == {
        "moving-average",
        "rsi-macd-candidate",
    }
    assert all(result.deterministic for result in results)
    assert all(result.plugin_api_version == "1.0" for result in results)
    candidate = next(result for result in results if result.plugin_id == "rsi-macd-candidate")
    assert candidate.candidate_disposition == "review_required"
