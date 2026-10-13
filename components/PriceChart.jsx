'use client'

import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

const EMPTY_BARS = []

export default function PriceChart({ data }) {
  const svgRef = useRef(null)
  const bars = Array.isArray(data?.bars) ? data.bars : EMPTY_BARS
  const lastBar = bars.length > 0 ? bars[bars.length - 1] : null
  const displayPrice = data?.price ?? (lastBar ? Number(lastBar.close) : null)
  const displayTimestamp = data?.timestamp ?? lastBar?.observed_at

  useEffect(() => {
    if (!svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    /** @type {Array<{ date: Date, price: number }>} */
    const priceData = bars
      .map((bar) => ({ date: new Date(bar.observed_at), price: Number(bar.close) }))
      .filter((item) => Number.isFinite(item.date.getTime()) && Number.isFinite(item.price))

    if (priceData.length === 0) return

    const margin = { top: 20, right: 20, bottom: 34, left: 54 }
    const width = 800 - margin.left - margin.right
    const height = 400 - margin.top - margin.bottom
    const chart = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)
    const x = d3.scaleTime()
      .domain([priceData[0].date, priceData[priceData.length - 1].date])
      .range([0, width])
    const prices = priceData.map((item) => item.price)
    const minimum = Math.min(...prices)
    const maximum = Math.max(...prices)
    const padding = Math.max((maximum - minimum) * 0.08, Math.abs(maximum) * 0.002, 0.01)
    const y = d3.scaleLinear()
      .domain([minimum - padding, maximum + padding])
      .nice()
      .range([height, 0])

    chart.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x).ticks(Math.min(priceData.length, 8)))
    chart.append('g').call(d3.axisLeft(y).ticks(6))

    /** @type {Array<[number, number]>} */
    const chartPoints = priceData.map((item) => [item.date.getTime(), item.price])
    const line = d3.line()
      .x((point) => x(point[0]))
      .y((point) => y(point[1]))
      .curve(d3.curveMonotoneX)

    chart.append('path')
      .datum(chartPoints)
      .attr('fill', 'none')
      .attr('stroke', '#4f46e5')
      .attr('stroke-width', 2)
      .attr('d', line)

    const last = priceData[priceData.length - 1]
    chart.append('circle')
      .attr('cx', x(last.date))
      .attr('cy', y(last.price))
      .attr('r', 4)
      .attr('fill', '#4f46e5')
  }, [bars])

  return (
    <section className="price-chart rounded-lg bg-white p-4 shadow-sm dark:bg-gray-800" aria-label="Historical market data">
      <h2 className="mb-1 text-xl font-bold">Market data: {data?.instrument ?? 'Unavailable'}</h2>
      <p className="mb-2 text-xs text-gray-600 dark:text-gray-300">
        Source: {data?.source_id ?? 'not available'} · {bars.length} OHLCV bars
      </p>
      {bars.length > 0 ? (
        <svg ref={svgRef} className="h-96 w-full" viewBox="0 0 800 400" role="img" aria-label={`${data?.instrument ?? 'Instrument'} closing prices from historical OHLCV bars`} />
      ) : (
        <p className="rounded border border-gray-300 p-6 text-sm text-gray-700 dark:border-gray-600 dark:text-gray-200">
          No valid historical bars are available for this view.
        </p>
      )}
      <div className="mt-2 flex flex-wrap justify-between gap-3 text-sm">
        <div>
          <div>Latest close: {Number.isFinite(Number(displayPrice)) ? Number(displayPrice).toFixed(2) : '—'}</div>
          <div>Observed: {displayTimestamp ? new Date(displayTimestamp).toLocaleString() : '—'}</div>
        </div>
        {data?.regime && <div>Simulated regime: {data.regime}</div>}
      </div>
    </section>
  )
}
