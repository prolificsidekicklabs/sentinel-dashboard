import {
  DEMO_AGENT_OPINIONS,
  DEMO_DISCOURSE_LOG,
  DEMO_MARKET_STATE,
} from "./demo-data";

describe("Sentinel synthetic demo data", () => {
  test("market fixture remains fixed and identifiable as a demo", () => {
    expect(DEMO_MARKET_STATE).toMatchObject({
      instrument: "SPY",
      price: 452.37,
      timestamp: "2026-10-11T23:00:00.000Z",
      regime: "trending",
    });
    expect(Object.isFrozen(DEMO_MARKET_STATE)).toBe(true);
  });

  test("agent and discourse fixtures use the same fixed timestamp", () => {
    const timestamps = DEMO_DISCOURSE_LOG.map((entry) => entry.timestamp);

    expect(DEMO_AGENT_OPINIONS).toHaveLength(5);
    expect(new Set(timestamps)).toEqual(
      new Set([DEMO_MARKET_STATE.timestamp]),
    );
    expect(Object.isFrozen(DEMO_AGENT_OPINIONS)).toBe(true);
    expect(Object.isFrozen(DEMO_DISCOURSE_LOG)).toBe(true);
  });
});
