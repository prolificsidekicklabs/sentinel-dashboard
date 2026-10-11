from __future__ import annotations

import asyncio
import importlib.util
import random
from pathlib import Path
from typing import Any

import pytest

from sentinel_core.contracts import PluginContext

PLUGIN_FILE = Path(__file__).resolve().parents[1] / "plugin.py"
PLUGIN_SPEC = importlib.util.spec_from_file_location(
    "moving_average_plugin_under_test", PLUGIN_FILE
)
assert PLUGIN_SPEC is not None and PLUGIN_SPEC.loader is not None
PLUGIN_MODULE = importlib.util.module_from_spec(PLUGIN_SPEC)
PLUGIN_SPEC.loader.exec_module(PLUGIN_MODULE)
MovingAveragePlugin = PLUGIN_MODULE.MovingAveragePlugin


def _context(input_data: dict[str, Any]) -> PluginContext:
    return PluginContext(
        plugin_id="moving-average",
        plugin_version="0.1.0",
        seed=7,
        input_data=input_data,
        rng=random.Random(7),
    )


def test_computes_trailing_average_without_claiming_a_trade_signal() -> None:
    result = asyncio.run(
        MovingAveragePlugin().run(
            _context({"instrument": "demo", "prices": [9, 10, 11, 12], "window": 3})
        )
    )

    assert result.output == {
        "instrument": "DEMO",
        "window": 3,
        "last_price": 12.0,
        "simple_moving_average": 11.0,
        "distance_pct": 9.0909090909,
    }


@pytest.mark.parametrize(
    "input_data",
    [
        {"prices": [1.0], "window": 2},
        {"prices": [1.0, float("nan")], "window": 2},
        {"prices": [1.0, 2.0], "window": True},
        {"prices": [1.0, 2.0], "window": 2, "instrument": " "},
    ],
)
def test_rejects_invalid_input(input_data: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        asyncio.run(MovingAveragePlugin().run(_context(input_data)))
