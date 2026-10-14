# Sentinel Plugin Contract v1.0

## Status and versioning

Sentinel currently supports **plugin API version `1.0`**. This contract version is independent of a plugin's own semantic `version` and of the YAML `manifest_version`.

Every installed plugin manifest declares `plugin_api_version: "1.0"`. The host validates that declaration before execution, passes it on `PluginContext`, and includes it in discovery and run responses. Unknown or mismatched API versions fail closed. A backward-incompatible contract change requires a new plugin API version; plugin releases continue to use semantic versions independently.

## Input and output boundary

The runtime starts a fresh bounded worker for each invocation. The v1.0 context contains:

- `plugin_id`, plugin `version`, `plugin_api_version`, and an explicit deterministic `seed`;
- a defensive copy of caller JSON, exposed as recursively read-only mappings and tuples;
- optionally, a `PluginMarketContextV1` with an instrument, timeframe, provider source, data-quality status, observation and receive timestamps, and chronological OHLCV bars.

The market context and each bar are frozen typed models; the bar collection is a tuple. Prices and volumes use finite `Decimal` values, timestamps must be timezone-aware, and the model checks instrument/source consistency, OHLC validity, bar order, and the latest-bar timestamp. The context schema contains no account, position, credential, provider client, order, or execution field. It exposes no implicit filesystem or network service. This read-only object contract is not itself a security sandbox.

A plugin returns a finite-JSON `PluginResult`. A generic result is only analysis data: it does not grant a permission or create an order. Strategy plugins cannot use the generic run API. The host parses strategy output into the strict `CandidateSignal` schema, evaluates it independently through `CandidateRiskGate`, and records the validated signal, review disposition, versions, market metadata, and output hash as `research.candidate.evaluated` in the local append-only audit chain. The response exposes the audit `record_id`. If recording fails, the endpoint returns an error instead of presenting an unrecorded result.

Candidate labels are research artifacts, not advice or forecasts. The gate can only block, report no candidate, or allow human review. The candidate, review, and top-level response all keep `execution_enabled: false`. No plugin can set an order side, quantity, risk approval, or execution authorization through this contract. The local hash chain is tamper-evident, not externally immutable storage.

## Offline deterministic validation

From `backend/`, run the reviewed fixtures with no provider credentials, market-data request, account access, or external service:

```bash
.venv/bin/python -m sentinel_core.validation_harness
```

The harness executes each built-in fixture twice in the bounded local worker with the same versioned input and seed, requires matching output digests, schema-validates candidate output, and independently runs the review-only gate against a fixed synthetic snapshot. A plugin without an explicit offline fixture causes validation to fail rather than being silently skipped. These checks establish software-contract consistency and determinism for the fixtures only; they do not establish strategy quality, predictive value, production isolation, or safety against hostile plugin code.

The normal backend formatting, lint, type-check, and full test commands remain in [backend setup](../README.md#verify). The OCI/gVisor runner for manifests marked untrusted continues to fail closed until its pinned image and runtime are operationally tested. Marketplace distribution, payments, and plugin-controlled live execution remain deferred.

## Constructor and mutation notes

The plugin context is created through its real dataclass constructor/factory and validated during construction; it does not rely on a custom `init` method that dataclasses never invoke. Candidate outputs use Pydantic construction-time validation and immutable nested reason-code tuples rather than a misspelled `post_init` hook or silent value clamping. Inputs described as read-only are copied and recursively frozen before the plugin receives them.
