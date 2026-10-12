import assert from 'node:assert/strict'
import test from 'node:test'

import { createSentinelApiProxy } from './sentinel-api-proxy.js'

const SERVER_KEY = 'test-server-api-key-with-sufficient-length-000001'

function fakeResponse() {
  return {
    headers: {},
    body: undefined,
    statusCode: undefined,
    setHeader(name, value) { this.headers[name] = value },
    status(code) { this.statusCode = code; return this },
    json(body) { this.body = body; return this },
  }
}

function request(overrides = {}) {
  return {
    method: 'GET',
    query: { resource: 'dashboard', symbol: 'SPY', days: '30' },
    headers: { host: '127.0.0.1:3000', origin: 'http://127.0.0.1:3000', 'sec-fetch-site': 'same-origin' },
    ...overrides,
  }
}

test('forwards one allowlisted read with the server-only bearer key and no caching', async () => {
  const observed = { url: '', authorization: '', redirect: '' }
  const handler = createSentinelApiProxy({
    env: { NODE_ENV: 'development', SENTINEL_API_KEY: SERVER_KEY },
    fetchImpl: async (url, options) => {
      observed.url = String(url)
      observed.authorization = new Headers(options?.headers).get('Authorization') ?? ''
      observed.redirect = options?.redirect ?? ''
      return Response.json({ mode: 'paper-read-only', execution_enabled: false })
    },
  })
  const res = fakeResponse()

  await handler(request(), res)

  assert.equal(res.statusCode, 200)
  assert.equal(res.headers['Cache-Control'], 'private, no-store, max-age=0')
  assert.equal(observed.url, 'http://127.0.0.1:8000/api/v1/paper/dashboard?symbol=SPY&days=30')
  assert.equal(observed.authorization, `Bearer ${SERVER_KEY}`)
  assert.equal(observed.redirect, 'error')
  assert.deepEqual(res.body, { mode: 'paper-read-only', execution_enabled: false })
  assert.equal(JSON.stringify(res.body).includes(SERVER_KEY), false)
})

test('allows only valid reads and same-origin browser requests', async () => {
  const handler = createSentinelApiProxy({
    env: { NODE_ENV: 'development', SENTINEL_API_KEY: SERVER_KEY },
    fetchImpl: async () => { throw new Error('fetch must not run') },
  })
  const crossOrigin = fakeResponse()
  await handler(request({ headers: { host: '127.0.0.1:3000', origin: 'https://attacker.example' } }), crossOrigin)
  assert.equal(crossOrigin.statusCode, 403)

  const badSymbol = fakeResponse()
  await handler(request({ query: { resource: 'dashboard', symbol: 'SPY?force=1', days: '30' } }), badSymbol)
  assert.equal(badSymbol.statusCode, 400)

  const arbitraryResource = fakeResponse()
  await handler(request({ query: { resource: 'plugins' } }), arbitraryResource)
  assert.equal(arbitraryResource.statusCode, 404)

  const writeAttempt = fakeResponse()
  await handler(request({ method: 'POST' }), writeAttempt)
  assert.equal(writeAttempt.statusCode, 405)
  assert.equal(writeAttempt.headers.Allow, 'GET')
})

test('requires a long server API key and accepts only a loopback backend URL', async () => {
  const missingKey = createSentinelApiProxy({ env: { NODE_ENV: 'development' }, fetchImpl: async () => { throw new Error('unexpected fetch') } })
  const missing = fakeResponse()
  await missingKey(request(), missing)
  assert.equal(missing.statusCode, 503)

  const remoteBackend = createSentinelApiProxy({
    env: { NODE_ENV: 'development', SENTINEL_API_KEY: SERVER_KEY, SENTINEL_API_BASE_URL: 'http://10.0.0.5:8000' },
    fetchImpl: async () => { throw new Error('unexpected fetch') },
  })
  const rejected = fakeResponse()
  await remoteBackend(request(), rejected)
  assert.equal(rejected.statusCode, 503)
})

test('keeps the paper-data proxy disabled in production by default', async () => {
  const handler = createSentinelApiProxy({
    env: { NODE_ENV: 'production', SENTINEL_API_KEY: SERVER_KEY },
    fetchImpl: async () => { throw new Error('production proxy must not fetch') },
  })
  const res = fakeResponse()
  await handler(request(), res)

  assert.equal(res.statusCode, 404)
  assert.equal(res.body.error, 'local paper-data proxy is disabled in production')
})
