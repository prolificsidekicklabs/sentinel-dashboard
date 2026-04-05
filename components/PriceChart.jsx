"use client"

import { useEffect, useRef } from 'react'
import * as d3 from 'd3'

export default function PriceChart({ data }) {
  const svgRef = useRef()

  useEffect(() => {
    if (!data || !svgRef.current) return

    const svg = d3.select(svgRef.current)
    svg.selectAll("*").remove()

    const margin = { top: 20, right: 20, bottom: 30, left: 40 }
    const width = 800 - margin.left - margin.right
    const height = 400 - margin.top - margin.bottom

    const chart = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

    // Generate mock price data
    const priceData = Array.from({ length: 100 }, (_, i) => (
      {
        date: new Date(Date.now() - (100 - i) * 60000),
        price: data.price + (Math.sin(i * 0.2) * 5) + (i % 20 === 0 ? 3 : 0)
      }
    ))

    const x = d3.scaleTime().domain(d3.extent(priceData, d => d.date)).range([0, width])
    const y = d3.scaleLinear().domain([
      d3.min(priceData, d => d.price) - 5,
      d3.max(priceData, d => d.price) + 5
    ]).range([height, 0])

    // Add X axis
    chart.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x))

    // Add Y axis
    chart.append('g').call(d3.axisLeft(y))

    // Add price line
    const line = d3.line().x(d => x(d.date)).y(d => y(d.price))
    chart.append('path')
      .datum(priceData)
      .attr('fill', 'none')
      .attr('stroke', '#4f46e5')
      .attr('stroke-width', 2)
      .attr('d', line)

    // Add current price marker
    chart.append('circle')
      .attr('cx', x(priceData[priceData.length - 1].date))
      .attr('cy', y(priceData[priceData.length - 1].price))
      .attr('r', 5)
      .attr('fill', data.regime === 'high_volatility' ? '#ef4444' :
                   data.regime === 'low_volatility' ? '#10b981' : '#f59e0b')

    // Add regime label
    chart.append('text')
      .attr('x', width - 100)
      .attr('y', 20)
      .attr('fill', data.regime === 'high_volatility' ? '#ef4444' :
                   data.regime === 'low_volatility' ? '#10b981' : '#f59e0b')
      .attr('font-weight', 'bold')
      .text(`Regime: ${data.regime}`)

  }, [data])

  return (
    <div className="price-chart p-4 bg-white dark:bg-gray-800 rounded-lg shadow">
      <h2 className="text-xl font-bold mb-4">Market Data: {data.instrument}</h2>
      <svg ref={svgRef} className="w-full h-96"></svg>
      <div className="mt-2 flex justify-between text-sm">
        <div>
          <div>Price: {data.price?.toFixed(2)}</div>
          <div>Timestamp: {new Date(data.timestamp).toLocaleString()}</div>
        </div>
        <div>
          <div>RSI: {data.indicators?.rsi?.toFixed(2)}</div>
          <div>Spread: {data.order_book?.spread?.toFixed(2)}</div>
          <div>Regime: {data.regime}</div>
        </div>
      </div>
    </div>
  )
}