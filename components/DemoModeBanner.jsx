export default function DemoModeBanner() {
  return (
    <aside
      role="note"
      aria-labelledby="demo-mode-title"
      className="mb-4 rounded-lg border border-amber-400 bg-amber-50 p-4 text-amber-950 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
    >
      <h1 id="demo-mode-title" className="font-bold uppercase tracking-wide">
        Simulated demo — not live data
      </h1>
      <p className="mt-1 text-sm">
        All displayed prices, indicators, sentiment, risk labels, agent opinions, and the BLOCK verdict are randomly generated or hard-coded examples. No live feed or real analysis/risk service is connected. The verdict is illustrative; it cannot authorize or block a real action. Do not rely on this dashboard for trading decisions.
      </p>
    </aside>
  )
}
