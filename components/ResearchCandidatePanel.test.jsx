import assert from 'node:assert/strict'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import ResearchCandidatePanel from './ResearchCandidatePanel'

test('candidate panel starts idle, requires a manual request, and labels the output research-only', () => {
  const html = renderToStaticMarkup(<ResearchCandidatePanel />)

  assert.match(html, /RSI\/MACD candidate review/)
  assert.match(html, /Research output, not investment advice or a buy\/sell instruction/)
  assert.match(html, /This check does not read account or position data/)
  assert.match(html, /Ticker/)
  assert.match(html, /No provider request has been made/)
  assert.match(html, /Run research-only check/)
  assert.doesNotMatch(html, /Place order|Buy now|Submit trade/i)
})

test('production build visibly disables local provider access', () => {
  const html = renderToStaticMarkup(<ResearchCandidatePanel isProduction />)

  assert.match(html, /Disabled in production/)
  assert.match(html, /local provider proxy is disabled in production/i)
})
