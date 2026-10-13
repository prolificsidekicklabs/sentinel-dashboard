function formatMoney(value, currency) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount)
  } catch {
    return `${currency} ${amount.toFixed(2)}`
  }
}

function formatQuantity(value) {
  const amount = Number(value)
  return Number.isFinite(amount)
    ? new Intl.NumberFormat('en-US', { maximumFractionDigits: 6 }).format(amount)
    : '—'
}

export default function PaperAccountPanel({ snapshot }) {
  const account = snapshot.account
  const currency = account.currency

  return (
    <section className="rounded-lg border border-blue-300 bg-white p-4 shadow-sm dark:border-blue-800 dark:bg-gray-800" aria-labelledby="paper-account-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="paper-account-title" className="text-xl font-bold">Paper account snapshot</h2>
          <p className="text-sm text-gray-600 dark:text-gray-300">
            Read-only view · captured {new Date(snapshot.captured_at).toLocaleString()}
          </p>
        </div>
        <span className="rounded-full border border-blue-600 px-3 py-1 text-xs font-semibold uppercase text-blue-800 dark:text-blue-200">
          Paper · no orders
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          ['Equity', account.equity],
          ['Cash', account.cash],
          ['Buying power', account.buying_power],
        ].map(([label, value]) => (
          <div key={label} className="rounded-md bg-gray-50 p-3 dark:bg-gray-900">
            <dt className="text-xs uppercase tracking-wide text-gray-600 dark:text-gray-300">{label}</dt>
            <dd className="mt-1 text-lg font-semibold">{formatMoney(value, currency)}</dd>
          </div>
        ))}
      </dl>

      <h3 className="mt-5 text-lg font-semibold">Open positions</h3>
      {snapshot.positions.length === 0 ? (
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">No open positions were returned by the paper account.</p>
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-left text-sm dark:divide-gray-700">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-gray-600 dark:text-gray-300">
                <th scope="col" className="px-2 py-2">Symbol</th>
                <th scope="col" className="px-2 py-2">Quantity</th>
                <th scope="col" className="px-2 py-2">Average entry</th>
                <th scope="col" className="px-2 py-2">Current price</th>
                <th scope="col" className="px-2 py-2">Market value</th>
                <th scope="col" className="px-2 py-2">Unrealized P/L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {snapshot.positions.map((position) => (
                <tr key={position.instrument_id}>
                  <th scope="row" className="whitespace-nowrap px-2 py-2 font-semibold">{position.instrument_id}</th>
                  <td className="px-2 py-2">{formatQuantity(position.quantity)}</td>
                  <td className="px-2 py-2">{formatMoney(position.average_entry_price, position.currency)}</td>
                  <td className="px-2 py-2">{formatMoney(position.current_price, position.currency)}</td>
                  <td className="px-2 py-2">{formatMoney(position.market_value, position.currency)}</td>
                  <td className={`px-2 py-2 ${Number(position.unrealized_pl) < 0 ? 'text-red-700 dark:text-red-300' : 'text-green-700 dark:text-green-300'}`}>
                    {formatMoney(position.unrealized_pl, position.currency)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
