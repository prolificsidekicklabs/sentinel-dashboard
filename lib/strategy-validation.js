export const ENGINE_VERSION = '0.2.0'
export const STRATEGY_ID = 'sma-crossover-long-only'
export const TRAIN_PERCENT = 70

const MAX_BARS = 50_000
const TRADING_SESSIONS_PER_YEAR = 252

function parseCsvRows(input) {
  const text = input.replace(/^\uFEFF/, '')
  const records = []
  let record = []
  let field = ''
  let inQuotes = false
  let afterQuote = false

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i]

    if (inQuotes) {
      if (char === '"' && text[i + 1] === '"') {
        field += '"'
        i += 1
      } else if (char === '"') {
        inQuotes = false
        afterQuote = true
      } else {
        field += char
      }
      continue
    }

    if (afterQuote) {
      if (char === ',') {
        record.push(field)
        field = ''
        afterQuote = false
      } else if (char === '\n' || char === '\r') {
        if (char === '\r' && text[i + 1] === '\n') i += 1
        record.push(field)
        if (record.some((value) => value.trim() !== '')) records.push(record)
        record = []
        field = ''
        afterQuote = false
      } else if (char !== ' ' && char !== '\t') {
        throw new Error('CSV contains unexpected characters after a closing quote.')
      }
      continue
    }

    if (char === '"') {
      if (field.length !== 0) throw new Error('CSV contains a quote inside an unquoted field.')
      inQuotes = true
    } else if (char === ',') {
      record.push(field)
      field = ''
    } else if (char === '\n' || char === '\r') {
      if (char === '\r' && text[i + 1] === '\n') i += 1
      record.push(field)
      if (record.some((value) => value.trim() !== '')) records.push(record)
      record = []
      field = ''
    } else {
      field += char
    }
  }

  if (inQuotes) throw new Error('CSV contains an unterminated quoted field.')
  if (field.length > 0 || record.length > 0) {
    record.push(field)
    if (record.some((value) => value.trim() !== '')) records.push(record)
  }
  return records
}

function parseNumber(value, label, rowNumber) {
  if (value === undefined || value.trim() === '') {
    throw new Error(`CSV row ${rowNumber}: ${label} is required.`)
  }
  const number = Number(value.trim())
  if (!Number.isFinite(number)) {
    throw new Error(`CSV row ${rowNumber}: ${label} must be a finite number.`)
  }
  return number
}

function parseUtcDate(value, context) {
  const dateOnly = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
  const utcTimestamp = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?Z$/.test(value)
  if (!dateOnly && !utcTimestamp) {
    throw new Error(`${context}: date must be YYYY-MM-DD or an ISO UTC timestamp ending in Z.`)
  }
  const timestamp = Date.parse(value)
  const day = value.slice(0, 10)
  const midnightTimestamp = Date.parse(`${day}T00:00:00.000Z`)
  if (!Number.isFinite(timestamp) || !Number.isFinite(midnightTimestamp)
    || new Date(midnightTimestamp).toISOString().slice(0, 10) !== day
    || new Date(timestamp).toISOString().slice(0, 10) !== day) {
    throw new Error(`${context}: date is not a valid UTC calendar date.`)
  }
  return { timestamp, date: new Date(timestamp).toISOString() }
}

/** Parse and validate a daily OHLCV CSV supplied by the user. */
export function parseOhlcvCsv(csvText) {
  if (typeof csvText !== 'string' || csvText.trim() === '') {
    throw new Error('Choose a non-empty CSV file.')
  }

  const rows = parseCsvRows(csvText)
  if (rows.length < 2) throw new Error('CSV must contain a header row and at least one data row.')
  if (rows.length - 1 > MAX_BARS) throw new Error(`CSV exceeds the ${MAX_BARS.toLocaleString()} daily-bar limit.`)

  const headers = rows[0].map((value) => value.trim().toLowerCase())
  if (headers.some((header) => header === '')) throw new Error('CSV headers must be non-empty.')
  if (new Set(headers).size !== headers.length) throw new Error('CSV contains duplicate column headers.')
  const findColumn = (candidates) => {
    const matches = headers.map((header, index) => candidates.includes(header) ? index : -1).filter((index) => index >= 0)
    if (matches.length > 1) throw new Error(`CSV contains ambiguous columns for ${candidates[0]}.`)
    return matches[0] ?? -1
  }
  const columns = {
    date: findColumn(['date', 'datetime', 'timestamp', 'time']),
    open: findColumn(['open']),
    high: findColumn(['high']),
    low: findColumn(['low']),
    close: findColumn(['close']),
    volume: findColumn(['volume']),
  }

  for (const name of ['date', 'open', 'high', 'low', 'close']) {
    if (columns[name] < 0) throw new Error(`CSV is missing a required column: ${name}.`)
  }

  const bars = []
  let previousTimestamp = -Infinity
  let previousUtcDay = ''

  for (let i = 1; i < rows.length; i += 1) {
    const row = rows[i]
    const rowNumber = i + 1
    if (row.length !== headers.length) {
      throw new Error(`CSV row ${rowNumber}: expected ${headers.length} columns but found ${row.length}.`)
    }
    const dateValue = row[columns.date]?.trim()
    if (!dateValue) throw new Error(`CSV row ${rowNumber}: date is required.`)
    const parsedDate = parseUtcDate(dateValue, `CSV row ${rowNumber}`)
    const timestamp = parsedDate.timestamp
    if (timestamp <= previousTimestamp) {
      throw new Error(`CSV row ${rowNumber}: bars must be strictly chronological with no duplicate timestamps.`)
    }

    const date = parsedDate.date
    const utcDay = date.slice(0, 10)
    if (utcDay === previousUtcDay) {
      throw new Error(`CSV row ${rowNumber}: multiple bars on one UTC date are not supported; provide daily bars only.`)
    }

    const open = parseNumber(row[columns.open], 'open', rowNumber)
    const high = parseNumber(row[columns.high], 'high', rowNumber)
    const low = parseNumber(row[columns.low], 'low', rowNumber)
    const close = parseNumber(row[columns.close], 'close', rowNumber)
    const volumeValue = columns.volume >= 0 ? row[columns.volume]?.trim() : ''
    const volume = volumeValue ? parseNumber(volumeValue, 'volume', rowNumber) : null

    if ([open, high, low, close].some((value) => value <= 0)) {
      throw new Error(`CSV row ${rowNumber}: OHLC prices must be greater than zero.`)
    }
    if (high < Math.max(open, close) || low > Math.min(open, close) || high < low) {
      throw new Error(`CSV row ${rowNumber}: OHLC values are inconsistent; high/low do not contain open and close.`)
    }
    if (volume !== null && volume < 0) throw new Error(`CSV row ${rowNumber}: volume cannot be negative.`)

    bars.push({ date, timestamp, open, high, low, close, volume })
    previousTimestamp = timestamp
    previousUtcDay = utcDay
  }

  if (bars.length < 3) throw new Error('At least 3 daily bars are required.')
  return bars
}

function validateBars(inputBars) {
  if (!Array.isArray(inputBars) || inputBars.length < 3) {
    throw new Error('At least 3 validated daily OHLC bars are required.')
  }
  if (inputBars.length > MAX_BARS) throw new Error(`Dataset exceeds the ${MAX_BARS.toLocaleString()} daily-bar limit.`)

  let previousTimestamp = -Infinity
  let previousUtcDay = ''
  return inputBars.map((bar, index) => {
    const parsedDate = parseUtcDate(bar.date, `Bar ${index + 1}`)
    const timestamp = parsedDate.timestamp
    if (timestamp <= previousTimestamp) throw new Error(`Bar ${index + 1}: bars must be strictly chronological.`)
    const date = parsedDate.date
    const utcDay = date.slice(0, 10)
    if (utcDay === previousUtcDay) throw new Error(`Bar ${index + 1}: multiple bars on one UTC date are not supported.`)

    const normalized = { ...bar, date, timestamp }
    for (const name of ['open', 'high', 'low', 'close']) {
      if (!Number.isFinite(normalized[name]) || normalized[name] <= 0) {
        throw new Error(`Bar ${index + 1}: ${name} must be a finite, positive price.`)
      }
    }
    if (normalized.high < Math.max(normalized.open, normalized.close)
      || normalized.low > Math.min(normalized.open, normalized.close)
      || normalized.high < normalized.low) {
      throw new Error(`Bar ${index + 1}: OHLC values are inconsistent.`)
    }
    if (normalized.volume !== null && normalized.volume !== undefined
      && (!Number.isFinite(normalized.volume) || normalized.volume < 0)) {
      throw new Error(`Bar ${index + 1}: volume must be finite and non-negative when supplied.`)
    }

    previousTimestamp = timestamp
    previousUtcDay = utcDay
    return normalized
  })
}

function validateConfiguration(config, barCount) {
  const readNumber = (key) => {
    const value = Number(config?.[key])
    if (!Number.isFinite(value)) throw new Error(`${key} must be a finite number.`)
    return value
  }

  const fastPeriod = readNumber('fastPeriod')
  const slowPeriod = readNumber('slowPeriod')
  const startingCapital = readNumber('startingCapital')
  const allocationPct = readNumber('allocationPct')
  const commissionBps = readNumber('commissionBps')
  const halfSpreadBps = readNumber('halfSpreadBps')
  const slippageBps = readNumber('slippageBps')
  const currencyCode = String(config?.currencyCode ?? 'USD').trim().toUpperCase()

  if (!/^[A-Z]{3}$/.test(currencyCode)) throw new Error('Currency code must be three letters and match the price data currency.')
  if (!Number.isInteger(fastPeriod) || fastPeriod < 2) throw new Error('Fast SMA period must be a whole number of at least 2 bars.')
  if (!Number.isInteger(slowPeriod) || slowPeriod <= fastPeriod) throw new Error('Slow SMA period must be a whole number greater than the fast period.')
  if (!(startingCapital > 0)) throw new Error('Starting capital must be greater than zero.')
  if (!(allocationPct > 0 && allocationPct <= 100)) throw new Error('Allocation must be greater than 0% and no more than 100%.')
  for (const [name, value] of Object.entries({ commissionBps, halfSpreadBps, slippageBps })) {
    if (value < 0 || value > 10_000) throw new Error(`${name} must be between 0 and 10,000 basis points per side.`)
  }
  if (halfSpreadBps + slippageBps >= 10_000) {
    throw new Error('Half-spread plus slippage must total less than 10,000 basis points per side.')
  }

  const splitIndex = Math.floor((barCount * TRAIN_PERCENT) / 100)
  if (splitIndex < slowPeriod + 2) {
    throw new Error(`The fixed ${TRAIN_PERCENT}/${100 - TRAIN_PERCENT} split needs at least ${Math.ceil((slowPeriod + 2) / (TRAIN_PERCENT / 100))} bars so the training segment has enough history for the slow SMA.`)
  }
  if (barCount - splitIndex < 3) throw new Error('The out-of-sample segment must contain at least 3 daily bars.')

  return {
    fastPeriod,
    slowPeriod,
    startingCapital,
    currencyCode,
    allocationPct,
    commissionBps,
    halfSpreadBps,
    slippageBps,
    splitIndex,
  }
}

function movingAverage(values, period) {
  const output = Array(values.length).fill(null)
  let rollingTotal = 0
  for (let i = 0; i < values.length; i += 1) {
    rollingTotal += values[i]
    if (i >= period) rollingTotal -= values[i - period]
    if (i >= period - 1) output[i] = rollingTotal / period
  }
  return output
}

function createSignals(bars, fastPeriod, slowPeriod) {
  const closes = bars.map((bar) => bar.close)
  const fast = movingAverage(closes, fastPeriod)
  const slow = movingAverage(closes, slowPeriod)
  const signals = Array(bars.length).fill(null)

  for (let i = 1; i < bars.length; i += 1) {
    if (fast[i - 1] === null || slow[i - 1] === null || fast[i] === null || slow[i] === null) continue
    if (fast[i - 1] <= slow[i - 1] && fast[i] > slow[i]) signals[i] = 'enter'
    else if (fast[i - 1] >= slow[i - 1] && fast[i] < slow[i]) signals[i] = 'exit'
  }
  return signals
}

function costsForFill(rawPrice, quantity, side, config) {
  const adverseRate = (config.halfSpreadBps + config.slippageBps) / 10_000
  const fillPrice = side === 'buy' ? rawPrice * (1 + adverseRate) : rawPrice * (1 - adverseRate)
  const halfSpread = quantity * rawPrice * config.halfSpreadBps / 10_000
  const slippage = quantity * rawPrice * config.slippageBps / 10_000
  const commission = quantity * fillPrice * config.commissionBps / 10_000
  return { fillPrice, halfSpread, slippage, commission, total: halfSpread + slippage + commission }
}

function buyPosition(cash, bar, barIndex, config) {
  const costRate = config.commissionBps / 10_000
  const adverseRate = (config.halfSpreadBps + config.slippageBps) / 10_000
  const fillPrice = bar.open * (1 + adverseRate)
  const budget = cash * (config.allocationPct / 100)
  const quantity = budget / (fillPrice * (1 + costRate))
  if (!(quantity > 0)) return null
  const fillCosts = costsForFill(bar.open, quantity, 'buy', config)
  const outflow = quantity * fillCosts.fillPrice + fillCosts.commission
  return {
    cash: Math.max(0, cash - outflow),
    position: {
      quantity,
      entryIndex: barIndex,
      entryDate: bar.date,
      entryRawPrice: bar.open,
      entryFillPrice: fillCosts.fillPrice,
      entryCosts: fillCosts,
      entryOutflow: outflow,
    },
  }
}

function sellPosition(cash, position, bar, barIndex, config, reason) {
  const exitCosts = costsForFill(bar.open ?? bar.close, position.quantity, 'sell', config)
  const exitRawPrice = bar.open ?? bar.close
  const proceeds = position.quantity * exitCosts.fillPrice - exitCosts.commission
  const netPnl = proceeds - position.entryOutflow
  const grossPnl = (exitRawPrice - position.entryRawPrice) * position.quantity
  const totalCosts = position.entryCosts.total + exitCosts.total
  const trade = {
    entryDate: position.entryDate,
    exitDate: bar.date,
    entryRawPrice: position.entryRawPrice,
    entryFillPrice: position.entryFillPrice,
    exitRawPrice,
    exitFillPrice: exitCosts.fillPrice,
    quantity: position.quantity,
    barsHeld: barIndex - position.entryIndex,
    grossPnl,
    netPnl,
    entryCosts: position.entryCosts,
    exitCosts,
    totalCosts,
    exitReason: reason,
  }
  return { cash: cash + proceeds, trade }
}

function metricSummary(curve, trades, startingCapital, totalCosts, startTimestamp, endTimestamp) {
  const finalEquity = curve.at(-1)?.equity ?? startingCapital
  const totalReturn = finalEquity / startingCapital - 1
  const elapsedDays = (endTimestamp - startTimestamp) / 86_400_000
  const cagr = elapsedDays > 0 && finalEquity > 0
    ? (finalEquity / startingCapital) ** (365.25 / elapsedDays) - 1
    : null

  const returns = []
  for (let i = 1; i < curve.length; i += 1) {
    const previous = curve[i - 1].equity
    if (previous > 0) returns.push(curve[i].equity / previous - 1)
  }
  const meanReturn = returns.length ? returns.reduce((sum, value) => sum + value, 0) / returns.length : null
  const variance = returns.length > 1
    ? returns.reduce((sum, value) => sum + ((value - meanReturn) ** 2), 0) / (returns.length - 1)
    : null
  const dailyVolatility = variance === null ? null : Math.sqrt(variance)
  const annualizedVolatility = dailyVolatility === null ? null : dailyVolatility * Math.sqrt(TRADING_SESSIONS_PER_YEAR)
  const sharpe = dailyVolatility > 0 && meanReturn !== null
    ? (meanReturn / dailyVolatility) * Math.sqrt(TRADING_SESSIONS_PER_YEAR)
    : null

  let peak = startingCapital
  let maxDrawdown = 0
  for (const point of curve) {
    peak = Math.max(peak, point.equity)
    if (peak > 0) maxDrawdown = Math.min(maxDrawdown, point.equity / peak - 1)
  }

  const wins = trades.filter((trade) => trade.netPnl > 0)
  const losses = trades.filter((trade) => trade.netPnl < 0)
  const grossWins = wins.reduce((sum, trade) => sum + trade.netPnl, 0)
  const grossLosses = Math.abs(losses.reduce((sum, trade) => sum + trade.netPnl, 0))
  const averageExposure = curve.length > 1
    ? curve.slice(1).reduce((sum, point) => sum + point.exposurePct, 0) / (curve.length - 1)
    : 0

  return {
    startingCapital,
    endingEquity: finalEquity,
    totalReturn,
    cagr,
    annualizedVolatility,
    sharpe,
    maxDrawdown,
    tradeCount: trades.length,
    winRate: trades.length ? wins.length / trades.length : null,
    profitFactor: grossLosses > 0 ? grossWins / grossLosses : null,
    expectancyPerTrade: trades.length ? trades.reduce((sum, trade) => sum + trade.netPnl, 0) / trades.length : null,
    averageExposure,
    totalCosts,
    riskFreeRate: 0,
    annualizationSessions: TRADING_SESSIONS_PER_YEAR,
    drawdownConvention: 'Peak-to-trough from marked-to-market equity; terminal liquidation costs included.',
  }
}

function runStrategySegment(bars, signals, startIndex, endIndex, config) {
  let cash = config.startingCapital
  let position = null
  let pendingOrder = null
  let totalCosts = 0
  const trades = []
  const equityCurve = [{ date: bars[startIndex].date, equity: config.startingCapital, exposurePct: 0 }]

  for (let i = startIndex; i < endIndex; i += 1) {
    const bar = bars[i]

    if (pendingOrder?.executeIndex === i) {
      if (pendingOrder.side === 'buy' && !position) {
        const execution = buyPosition(cash, bar, i, config)
        if (execution) {
          cash = execution.cash
          position = execution.position
          totalCosts += position.entryCosts.total
        }
      } else if (pendingOrder.side === 'sell' && position) {
        const execution = sellPosition(cash, position, bar, i, config, 'sma-cross-down-next-open')
        cash = execution.cash
        totalCosts += execution.trade.exitCosts.total
        trades.push(execution.trade)
        position = null
      }
      pendingOrder = null
    }

    if (i === endIndex - 1 && position) {
      const terminalBar = { ...bar, open: bar.close }
      const execution = sellPosition(cash, position, terminalBar, i, config, 'end-of-test-liquidation-estimate')
      cash = execution.cash
      totalCosts += execution.trade.exitCosts.total
      trades.push(execution.trade)
      position = null
    }

    const equity = cash + (position ? position.quantity * bar.close : 0)
    const exposurePct = equity > 0 && position ? (position.quantity * bar.close) / equity : 0
    equityCurve.push({ date: bar.date, equity, exposurePct })

    if (i < endIndex - 1) {
      if (signals[i] === 'enter' && !position) pendingOrder = { side: 'buy', executeIndex: i + 1 }
      else if (signals[i] === 'exit' && position) pendingOrder = { side: 'sell', executeIndex: i + 1 }
    }
  }

  return {
    metrics: metricSummary(
      equityCurve,
      trades,
      config.startingCapital,
      totalCosts,
      bars[startIndex].timestamp,
      bars[endIndex - 1].timestamp,
    ),
    trades,
    equityCurve,
  }
}

function runBuyAndHoldSegment(bars, startIndex, endIndex, config) {
  const firstBar = bars[startIndex]
  const lastBar = bars[endIndex - 1]
  const openingExecution = buyPosition(config.startingCapital, firstBar, startIndex, config)
  const position = openingExecution.position
  let cash = openingExecution.cash
  let totalCosts = position.entryCosts.total
  const equityCurve = [{ date: firstBar.date, equity: config.startingCapital, exposurePct: 0 }]
  const trades = []

  for (let i = startIndex; i < endIndex; i += 1) {
    const bar = bars[i]
    if (i === endIndex - 1) {
      const terminalBar = { ...bar, open: bar.close }
      const execution = sellPosition(cash, position, terminalBar, i, config, 'benchmark-end-of-test-liquidation-estimate')
      cash = execution.cash
      totalCosts += execution.trade.exitCosts.total
      trades.push(execution.trade)
      equityCurve.push({ date: bar.date, equity: cash, exposurePct: 0 })
    } else {
      const equity = cash + position.quantity * bar.close
      equityCurve.push({
        date: bar.date,
        equity,
        exposurePct: equity > 0 ? (position.quantity * bar.close) / equity : 0,
      })
    }
  }

  return {
    metrics: metricSummary(
      equityCurve,
      trades,
      config.startingCapital,
      totalCosts,
      firstBar.timestamp,
      lastBar.timestamp,
    ),
    trades,
    equityCurve,
  }
}

/**
 * Run one deterministic long-only SMA crossover experiment on validated daily bars.
 * Signal is computed at close and filled at the next bar's open, with adverse
 * half-spread, slippage, and commission charged on entry and exit.
 */
export function runValidation(inputBars, configuration) {
  const bars = validateBars(inputBars)
  const config = validateConfiguration(configuration, bars.length)
  const signals = createSignals(bars, config.fastPeriod, config.slowPeriod)
  const splitIndex = config.splitIndex
  const train = {
    startDate: bars[0].date,
    endDate: bars[splitIndex - 1].date,
    barCount: splitIndex,
    strategy: runStrategySegment(bars, signals, 0, splitIndex, config),
    buyAndHold: runBuyAndHoldSegment(bars, 0, splitIndex, config),
  }
  const outOfSample = {
    startDate: bars[splitIndex].date,
    endDate: bars[bars.length - 1].date,
    barCount: bars.length - splitIndex,
    strategy: runStrategySegment(bars, signals, splitIndex, bars.length, config),
    buyAndHold: runBuyAndHoldSegment(bars, splitIndex, bars.length, config),
  }

  return {
    schemaVersion: 'sentinel-strategy-experiment.v1',
    engineVersion: ENGINE_VERSION,
    strategy: {
      id: STRATEGY_ID,
      name: 'Long-only simple moving-average crossover',
      entryRule: `Enter long when the ${config.fastPeriod}-bar SMA crosses above the ${config.slowPeriod}-bar SMA at a daily close.`,
      exitRule: `Exit at the next daily open after the ${config.fastPeriod}-bar SMA crosses below the ${config.slowPeriod}-bar SMA at a daily close.`,
      sizingRule: `Invest up to ${config.allocationPct}% of available cash in one long position; fractional units; no leverage or shorting.`,
    },
    assumptions: {
      barFrequency: 'One daily OHLC bar per UTC date; no intraday support.',
      marketScope: 'Equity-style daily sessions using 252 sessions per year; 24/7 or other asset classes require a separately reviewed annualization and execution model.',
      decisionTiming: 'Signal uses the completed daily close; execution is at the following bar open.',
      fillModel: 'Adverse price adjustment on each side: user-provided half-spread + slippage; commission charged on filled notional.',
      positionPolicy: 'One long position maximum; cash funded; no leverage, shorts, stops, or pyramiding.',
      terminalValuation: 'Any open position is valued with an estimated adverse-cost liquidation at the segment final close; this is a valuation convention, not a promised fill.',
      benchmark: 'Buy-and-hold from the segment first open through final close, using the same allocation and cost assumptions.',
      riskMetrics: 'Zero risk-free rate; 252 trading sessions per year; Sharpe uses sample standard deviation of daily marked-to-market returns.',
      profitFactorConvention: 'Null when no losing trades occurred; this does not imply an infinite or validated edge.',
      currency: 'All prices, capital, costs, and P&L use the supplied currency code; no foreign-exchange conversion is applied.',
      omissions: ['No taxes, dividends, corporate-action processing, market impact, borrow/funding costs, partial fills, halts, or venue-specific lot rules.'],
    },
    configuration: {
      fastPeriod: config.fastPeriod,
      slowPeriod: config.slowPeriod,
      startingCapital: config.startingCapital,
      currencyCode: config.currencyCode,
      allocationPct: config.allocationPct,
      costsBpsPerSide: {
        commission: config.commissionBps,
        halfSpread: config.halfSpreadBps,
        slippage: config.slippageBps,
      },
      annualizationSessions: TRADING_SESSIONS_PER_YEAR,
      riskFreeRate: 0,
    },
    dataset: {
      barCount: bars.length,
      firstDate: bars[0].date,
      lastDate: bars[bars.length - 1].date,
      dataHandling: 'Input supplied by user; validated but not independently sourced or authenticated.',
    },
    split: {
      method: 'chronological-holdout',
      trainPercent: TRAIN_PERCENT,
      outOfSamplePercent: 100 - TRAIN_PERCENT,
      trainEndDate: bars[splitIndex - 1].date,
      outOfSampleStartDate: bars[splitIndex].date,
      trainingBarCount: splitIndex,
      outOfSampleBarCount: bars.length - splitIndex,
      indicatorWarmup: 'Moving averages may use only prior historical bars before the holdout; positions reset flat at the holdout boundary; no training-period signal is carried into the test segment.',
    },
    inSample: train,
    outOfSample,
    caveats: [
      'Prototype metrics are descriptive, not evidence of a durable edge or an investment recommendation.',
      'Do not tune on or repeatedly inspect the out-of-sample segment; doing so invalidates it as a holdout.',
      'No statistical significance, multiple-testing correction, or robustness/regime analysis is implemented.',
      'The input data source, timestamps, corporate actions, and survivorship properties are not independently verified.',
      'There is no paper-trading or live-order integration.',
    ],
  }
}

/** Stable identity content; createdAt and source filename are intentionally excluded. */
export function experimentIdentityPayload(experiment, sourceSha256) {
  return {
    schemaVersion: experiment.schemaVersion,
    engineVersion: experiment.engineVersion,
    sourceSha256,
    dataset: experiment.dataset,
    strategy: experiment.strategy,
    configuration: experiment.configuration,
    split: experiment.split,
    assumptions: experiment.assumptions,
    inSample: experiment.inSample,
    outOfSample: experiment.outOfSample,
    caveats: experiment.caveats,
  }
}
