const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000'
const MINIMUM_API_KEY_LENGTH = 32
const ALLOWED_SYMBOL = /^[A-Za-z0-9.\-]{1,20}$/

function json(res, status, body) {
  return res.status(status).json(body)
}

function localBackendOrigin(env) {
  const raw = env.SENTINEL_API_BASE_URL || DEFAULT_BACKEND_URL
  try {
    const url = new URL(raw)
    if (
      url.protocol !== 'http:' ||
      !['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) ||
      url.username ||
      url.password ||
      url.pathname !== '/' ||
      url.search ||
      url.hash
    ) {
      return null
    }
    return url.origin
  } catch {
    return null
  }
}

function safeStatusMessage(status) {
  if (status === 401 || status === 403) return 'local API authentication failed'
  if (status === 422) return 'paper data request was rejected as invalid'
  if (status === 503) return 'paper data service is not configured'
  return 'paper data service request failed'
}

export function createSentinelApiProxy({ env = process.env, fetchImpl = fetch } = {}) {
  return async function sentinelApiProxy(req, res) {
    res.setHeader('Cache-Control', 'private, no-store, max-age=0')
    res.setHeader('Pragma', 'no-cache')
    res.setHeader('Vary', 'Origin')

    if (env.NODE_ENV === 'production') {
      return json(res, 404, { error: 'local paper-data proxy is disabled in production' })
    }
    if (req.method !== 'GET') {
      res.setHeader('Allow', 'GET')
      return json(res, 405, { error: 'method not allowed' })
    }

    const origin = req.headers?.origin
    if (origin) {
      try {
        if (new URL(origin).host !== req.headers.host) {
          return json(res, 403, { error: 'same-origin request required' })
        }
      } catch {
        return json(res, 403, { error: 'same-origin request required' })
      }
    }
    const fetchSite = req.headers?.['sec-fetch-site']
    if (fetchSite && fetchSite !== 'same-origin') {
      return json(res, 403, { error: 'same-origin request required' })
    }

    const resource = req.query?.resource
    if (resource !== 'dashboard') {
      return json(res, 404, { error: 'resource not found' })
    }

    const symbol = typeof req.query.symbol === 'string' ? req.query.symbol : 'SPY'
    const daysText = typeof req.query.days === 'string' ? req.query.days : '30'
    const days = Number(daysText)
    if (!ALLOWED_SYMBOL.test(symbol) || !Number.isInteger(days) || days < 1 || days > 365) {
      return json(res, 400, { error: 'invalid paper dashboard query' })
    }

    const apiKey = env.SENTINEL_API_KEY || ''
    if (apiKey.length < MINIMUM_API_KEY_LENGTH) {
      return json(res, 503, { error: 'local API authentication is not configured' })
    }
    const backendOrigin = localBackendOrigin(env)
    if (!backendOrigin) {
      return json(res, 503, { error: 'local API endpoint must use loopback HTTP' })
    }

    const target = new URL('/api/v1/paper/dashboard', backendOrigin)
    target.searchParams.set('symbol', symbol.toUpperCase())
    target.searchParams.set('days', String(days))

    let upstream
    try {
      upstream = await fetchImpl(target, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${apiKey}`,
        },
        redirect: 'error',
        cache: 'no-store',
        signal: AbortSignal.timeout(25_000),
      })
    } catch {
      return json(res, 502, { error: 'local paper API is unavailable' })
    }

    if (!upstream.ok) {
      const status = [401, 403, 422, 502, 503].includes(upstream.status)
        ? upstream.status
        : 502
      return json(res, status, { error: safeStatusMessage(status) })
    }

    let body
    try {
      body = await upstream.json()
    } catch {
      return json(res, 502, { error: 'local paper API returned invalid JSON' })
    }
    return json(res, 200, body)
  }
}
