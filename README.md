# Sentinel Dashboard

**Game-inspired trading intelligence interface**

Sentinel Dashboard is a React-based interface for exploring market-state information, analytical agent opinions, agent discourse, risk visualization, and decision-oriented trading workflows.

> **Current implementation status:** The reviewed dashboard uses simulated market data and predefined agent opinions. It is a UI prototype, not a verified live-market intelligence platform or an execution-ready trading system.

## 1. Project Goals

Sentinel aims to provide a visual workspace for examining:

- Market prices, indicators, and market-regime labels.
- Specialized analytical perspectives, such as technical, macroeconomic, microstructure, sentiment, and fundamental analysis.
- Agent opinions, stated confidence, rationales, and referenced data fields.
- Challenges, agreements, and decision events.
- Risk status and focused analysis views.
- Future integration with governed trading-intelligence services.

The longer-term direction is to evolve from a demonstration interface into a reliable, evidence-grounded trading-intelligence application with explicit risk controls and auditable decisions.

## 2. Current Capabilities

The reviewed source includes:

| Component | Current purpose |
|---|---|
| `pages/index.jsx` | Dashboard composition, local state, and simulated data initialization |
| `components/PriceChart.jsx` | D3-based price chart and market-state display |
| `components/AgentRoster.jsx` | Analytical-agent opinion cards |
| `components/DiscourseTimeline.jsx` | Timeline of opinions, challenges, agreements, and decisions |
| `components/FocusMode.jsx` | Detail panel for the first predefined analytical perspective |
| `components/CommandWheel.jsx` | Animated command-wheel interface |
| `components/EventRail.jsx` | Horizontal event stream |
| `components/RiskGlow.jsx` | Visual risk-level indicator |

The interface uses Next.js, React, Tailwind CSS, D3, and Framer Motion.

## 3. What Is Not Yet Verified

The reviewed code does not establish the existence of:

- A live market-data provider.
- A broker connection or order-execution engine.
- Persistent storage for analyses, decisions, or trades.
- A production agent-orchestration backend.
- An authenticated API for trading intelligence.
- A verified portfolio, position, or account-risk model.
- A tested integration with AEGIS Core.
- A production-grade audit trail or authorization system.

The presence of simulated opinions and a `BLOCK` verdict does not establish that a real governance or trading-risk engine evaluated the market.

## 4. Technology Stack

The package manifest declares:

- Next.js `16.0.0`
- React `18.2.x`
- Tailwind CSS `3.4.x`
- D3 `7.8.x`
- Framer Motion `11.x`
- TypeScript `5.3.x`
- Jest `29.7.x`
- Storybook `7.6.x`

The declared versions and scripts should be validated together before relying on development, lint, type-check, test, or build commands.

## 5. Prerequisites

Install a supported Node.js LTS version compatible with the selected Next.js release, plus npm. Confirm the project's `engines` field and Next.js compatibility requirements once dependency and runtime policy have been established.

## 6. Local Setup

Clone the repository and install its dependencies:

```bash
git clone https://github.com/prolificsidekicklabs/sentinel-dashboard.git
cd sentinel-dashboard
npm install
```

Start the development server:

```bash
npm run dev
```

Open `http://localhost:3000`.

Run the available project scripts:

```bash
npm run build
npm run start
npm test
npm run type-check
npm run lint
```

**Verification status:** These commands were attempted on 2026-10-11 and currently fail; see the [Development Guide](docs/DEVELOPMENT.md) for the exact results and outstanding configuration issues.

## 7. Architecture and Development Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Proposed API Contract](docs/API_CONTRACT.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Product Roadmap](docs/ROADMAP.md)
- [Contributing Guide](docs/CONTRIBUTING.md)

The API, deployment architecture, threat controls, and roadmap describe proposed implementation direction unless explicitly identified as current code behavior.

## 8. Safety and Financial Disclaimer

This software is not represented as a validated investment adviser, broker, execution platform, or source of reliable real-time financial data.

Simulated prices, agent outputs, confidence values, and risk labels must not be used to make actual trading decisions. Before any live-market use, implement and independently test data provenance, risk limits, authorization, monitoring, failure handling, and operational controls.

## 9. Documentation Status

This documentation is a proposed repository baseline prepared from a source review. Actual local verification attempts and their results are recorded in [the Development Guide](docs/DEVELOPMENT.md). The application is not build- or test-verified: the documented lint, type-check, test, and build commands currently fail, and deployment, security, and integration claims remain unverified.

Last reviewed: 2026-10-11.
