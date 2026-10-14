"""Deterministic, local-only simple moving-average example plugin."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from sentinel_core.contracts import PluginContext, PluginResult


class MovingAveragePlugin:
    """Compute a trailing SMA from an explicitly supplied sequence of prices."""

    async def run(self, context: PluginContext) -> PluginResult:
        data = context.input_data
        prices: Any = data.get("prices")
        window: Any = data.get("window")
        instrument: Any = data.get("instrument", "UNKNOWN")

        if not isinstance(prices, Sequence) or isinstance(prices, (str, bytes)) or len(prices) < 2:
            raise ValueError("prices must be a sequence containing at least two values")
        if type(window) is not int or window < 2 or window > len(prices):
            raise ValueError("window must be an integer from 2 through the number of prices")
        if not isinstance(instrument, str) or not instrument.strip():
            raise ValueError("instrument must be a non-empty string")

        normalized: list[float] = []
        for index, price in enumerate(prices):
            if isinstance(price, bool) or not isinstance(price, (int, float)):
                raise ValueError(f"prices[{index}] must be a finite positive number")
            numeric_price = float(price)
            if not math.isfinite(numeric_price) or numeric_price <= 0:
                raise ValueError(f"prices[{index}] must be a finite positive number")
            normalized.append(numeric_price)

        trailing_prices = normalized[-window:]
        average = sum(trailing_prices) / window
        last_price = normalized[-1]
        return PluginResult(
            output={
                "instrument": instrument.strip().upper(),
                "window": window,
                "last_price": round(last_price, 10),
                "simple_moving_average": round(average, 10),
                "distance_pct": round((last_price / average - 1) * 100, 10),
            }
        )
