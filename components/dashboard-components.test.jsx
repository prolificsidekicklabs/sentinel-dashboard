import assert from 'node:assert/strict'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import AgentRoster from './AgentRoster'
import CommandWheel from './CommandWheel'
import DemoModeBanner from './DemoModeBanner'
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

test('agent cards render simulated opinion, confidence, rationale, and evidence', () => {
  const html = renderToStaticMarkup(<AgentRoster agents={agents} />)

  assert.match(html, /Simulated Agent Opinions/)
  assert.match(html, /Confidence: 90%/)
  assert.match(html, /RSI indicates overbought conditions\./)
  assert.match(html, /indicators\.rsi/)
})

test('dashboard warning identifies synthetic data and the illustrative verdict', () => {
  const html = renderToStaticMarkup(<DemoModeBanner />)

  assert.match(html, /Simulated demo — not live data/i)
  assert.match(html, /randomly generated or hard-coded examples/)
  assert.match(html, /BLOCK verdict/)
  assert.match(html, /cannot authorize or block a real action/)
})

test('command menu describes demo-only behavior and links to local research tools', () => {
  const html = renderToStaticMarkup(<CommandWheel onClose={() => {}} onStatusMessage={() => {}} />)

  assert.match(html, /Demo-only actions/)
  assert.match(html, /href="\/strategy-validation"/)
  assert.match(html, /href="\/strategy-validation#cost-assumptions"/)
  assert.match(html, /Research Mode/)
  assert.match(html, /Cost Awareness/)
  assert.doesNotMatch(html, /alert\(/i)
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

test('discourse events render simulated actor, target, and message', () => {
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

  assert.match(html, /Simulated Agent Discourse/)
  assert.match(html, /Fed data contradicts RSI\./)
  assert.match(html, /MACRO/)
  assert.match(html, /TECH/)
})
