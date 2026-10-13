import { z } from 'zod'

const decimalText = z.string().regex(/^-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/)
const timestamp = z.string().datetime({ offset: true })

const barSchema = z.object({
  instrument_id: z.string().min(1).max(20),
  observed_at: timestamp,
  open: decimalText,
  high: decimalText,
  low: decimalText,
  close: decimalText,
  volume: decimalText.nullable(),
  currency: z.string().min(1).max(8),
  source_id: z.string().min(1).max(100),
}).strict()

const marketSchema = z.object({
  instrument_id: z.string().min(1).max(20),
  timeframe: z.string().min(1).max(20),
  source_id: z.string().min(1).max(100),
  observed_at: timestamp,
  received_at: timestamp,
  quality: z.enum(['valid', 'stale', 'incomplete', 'invalid', 'unavailable']),
  bars: z.array(barSchema).max(20_000),
}).strict()

const accountSchema = z.object({
  paper: z.literal(true),
  currency: z.string().min(1).max(8),
  equity: decimalText,
  cash: decimalText,
  buying_power: decimalText,
  observed_at: timestamp,
}).strict()

const positionSchema = z.object({
  instrument_id: z.string().min(1).max(20),
  quantity: decimalText,
  average_entry_price: decimalText,
  current_price: decimalText,
  market_value: decimalText,
  unrealized_pl: decimalText,
  currency: z.string().min(1).max(8),
}).strict()

export const paperDashboardSchema = z.object({
  mode: z.literal('paper-read-only'),
  execution_enabled: z.literal(false),
  captured_at: timestamp,
  market: marketSchema,
  account: accountSchema,
  positions: z.array(positionSchema).max(10_000),
}).strict()

export function parsePaperDashboard(value) {
  return paperDashboardSchema.parse(value)
}

export function toMarketChartData(snapshot) {
  const latest = snapshot.market.bars.at(-1)
  return {
    instrument: snapshot.market.instrument_id,
    timestamp: latest?.observed_at ?? snapshot.market.observed_at,
    price: latest ? Number(latest.close) : null,
    source_id: snapshot.market.source_id,
    bars: snapshot.market.bars,
    quality: snapshot.market.quality,
  }
}
