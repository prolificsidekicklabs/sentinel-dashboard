# Contributing to Sentinel Dashboard

## 1. Purpose

This guide defines the proposed contribution process for improving Sentinel Dashboard while preserving code quality, evidence discipline, and safety boundaries.

## 2. Before Starting

- Read `README.md`.
- Review `docs/ARCHITECTURE.md`.
- Review the relevant API or security documentation before changing interfaces or trust boundaries.
- Search existing issues and pull requests for related work.
- Confirm that the requested behavior is within the project's current implementation scope.

For trading-related changes, explicitly identify whether the work concerns visualization, analysis, governance, paper trading, or live execution.

## 3. Branching

Use focused branches, for example:

```text
docs/improve-architecture
fix/focus-mode-rendering
feature/market-snapshot-contract
test/agent-assessment-validation
```

Avoid combining unrelated refactors, new features, and documentation changes in one pull request unless the changes are inseparable.

## 4. Code Standards

- Follow existing JavaScript and JSX conventions unless a migration is approved.
- Prefer small, focused components.
- Validate data at application boundaries.
- Handle loading, empty, stale, invalid, and error states.
- Avoid hidden side effects in rendering code.
- Use stable identifiers for persisted or externally sourced records.
- Avoid logging sensitive data.
- Keep credentials and privileged configuration out of client code.
- Add comments where intent or a non-obvious safety assumption needs explanation.

## 5. Testing Requirements

Include tests appropriate to the change:

- Unit tests for transformations and business rules.
- Component tests for rendering and interactions.
- Contract tests for schemas and service boundaries.
- Integration tests for multi-component workflows.
- Failure-path tests for invalid data and unavailable dependencies.

For trading-related code, include tests showing that stale inputs, missing evidence, failed risk checks, and denied authorization do not result in approval.

## 6. Documentation Requirements

Update documentation when a change affects:

- Architecture or trust boundaries.
- Public interfaces or schemas.
- Setup or runtime requirements.
- Environment variables.
- Deployment procedures.
- Security assumptions.
- Product behavior or roadmap status.

Clearly label proposed behavior versus implemented behavior.

## 7. Pull Request Checklist

- [ ] The purpose and scope are clear.
- [ ] Related issues are referenced.
- [ ] Tests were added or updated.
- [ ] Relevant checks were run.
- [ ] Failure behavior was considered.
- [ ] No secrets or sensitive information were committed.
- [ ] Documentation was updated.
- [ ] Screenshots or recordings are included for significant UI changes.
- [ ] Risks, limitations, and follow-up tasks are disclosed.

Do not claim a check passed unless it was actually run and passed.

## 8. Security Reporting

Do not publish credentials, exploit details, private financial data, or sensitive vulnerability information in a public issue.

Use a private reporting channel configured by repository maintainers. If no private channel exists, repository maintainers should establish one before the application handles sensitive data or privileged integrations.

## 9. Review Principles

Reviewers should consider:

- Correctness and maintainability.
- Data provenance and schema validity.
- User experience and accessibility.
- Failure handling.
- Security and least privilege.
- Test quality.
- Compatibility and migration impact.
- Whether documentation accurately reflects the code.

For changes affecting trading decisions, risk policy, or execution permissions, require an additional domain and safety review.

## 10. Definition of Done

A contribution is complete when its intended behavior is implemented, relevant tests and checks have been run, documentation is accurate, security implications have been considered, and the approved review process is complete.
