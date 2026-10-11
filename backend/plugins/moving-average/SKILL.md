# Moving Average Indicator

## Purpose

A small, deterministic example Sentinel plugin that calculates a simple moving average from prices explicitly included in the request. It is a software-contract example only, not a validated market signal or investment recommendation.

## Interface

- Manifest: `sentinel_manifest.yaml`
- Entrypoint: `plugin:MovingAveragePlugin`
- Async method: `run(context: PluginContext) -> PluginResult`
- Required JSON input keys: `prices` (a non-empty list of finite, positive numbers) and `window` (an integer from 2 through the number of prices)
- Optional JSON input key: `instrument` (string, defaults to `UNKNOWN`)
- Permissions: none

The plugin receives no implicit network, broker, database, or provider client. Keep data provenance and authorization outside this indicator. Add or update tests in `tests/` when changing input or output behavior.
