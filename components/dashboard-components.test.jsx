import assert from 'node:assert/strict'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import AgentRoster from './AgentRoster'
import DiscourseTimeline from './DiscourseTimeline'
import FocusMode from './FocusMode'

const agents = [
  {
    agent_name: 'TECH',
    opinion: 'RED',
    confidence: 0.9,
    rationale: 'RSI indicates overbought conditions.',
    data_used: ['indicators.rsi'],
  },
]

test('agent cards render opinion, confidence, rationale, and evidence', () => {
  const html = renderToStaticMarkup(<AgentRoster agents={agents} />)

  assert.match(html, /Analytical Agents/)
  assert.match(html, /Confidence: 90%/)
  assert.match(html, /RSI indicates overbought conditions\./)
  assert.match(html, /indicators\.rsi/)
})

test('Focus Mode renders the market snapshot and agent opinion', () => {
  const html = renderToStaticMarkup(
    <FocusMode
      data={{
        marketState: { instrument: 'SPY', price: 450 },
        agents,
      }}
      onClose={() => {}}
    />,
  )

  assert.match(html, /Focus Mode: TECH/)
  assert.match(html, /&quot;instrument&quot;/)
  assert.match(html, /bg-red-100 text-red-800/)
  assert.doesNotMatch(html, /text-xs \$/)
})

test('discourse events render their actor, target, and message', () => {
  const html = renderToStaticMarkup(
    <DiscourseTimeline
      log={[
        {
          type: 'CHALLENGE',
          agent: 'MACRO',
          target: 'TECH',
          message: 'Fed data contradicts RSI.',
          timestamp: '2026-10-11T14:30:00.000Z',
        },
      ]}
    />,
  )

  assert.match(html, /Agent Discourse/)
  assert.match(html, /Fed data contradicts RSI\./)
  assert.match(html, /MACRO/)
  assert.match(html, /TECH/)
})
