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

function safeStatusMessage(status, resource) {
  if (status === 401 || status === 403) return 'local API authentication failed'
  if (status === 404) return 'local API route is unavailable'
  if (status === 422) return 'local read request was rejected as invalid'
  if (status === 503) return 'local API or provider is not configured'
  if (status === 502 && resource === 'research-candidate') return 'candidate market-data evaluation failed'
  return 'local paper API request failed'
}

function invalidQuery(query, allowedKeys) {
  return Object.keys(query).some((key) => !allowedKeys.has(key))
}

export function createSentinelApiProxy({ env = process.env, fetchImpl = fetch } = {}) {
  return async function sentinelApiProxy(req, res) {
    res.setHeader('Cache-Control', 'private, no-store, max-age=0')
    res.setHeader('Pragma', 'no-cache')
    res.setHeader('Vary', 'Origin')

    if (env.NODE_ENV === 'production') {
      return json(res, 404, { error: 'local provider proxy is disabled in production' })
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
    if (resource !== 'dashboard' && resource !== 'research-candidate') {
      return json(res, 404, { error: 'resource not found' })
    }

    const query = req.query ?? {}
    const allowedKeys = resource === 'dashboard'
      ? new Set(['resource', 'symbol', 'days'])
      : new Set(['resource', 'symbol'])
    if (invalidQuery(query, allowedKeys)) {
      return json(res, 400, { error: 'invalid request query' })
    }

    const rawSymbol = query.symbol
    const symbol = rawSymbol === undefined ? 'SPY' : rawSymbol
    if (typeof symbol !== 'string' || !ALLOWED_SYMBOL.test(symbol)) {
      return json(res, 400, { error: 'invalid ticker symbol' })
    }

    let targetPath
    let days
    if (resource === 'dashboard') {
      const rawDays = query.days
      const daysText = rawDays === undefined ? '30' : rawDays
      days = typeof daysText === 'string' ? Number(daysText) : Number.NaN
      if (!Number.isInteger(days) || days < 1 || days > 365) {
        return json(res, 400, { error: 'invalid paper dashboard query' })
      }
      targetPath = '/api/v1/paper/dashboard'
    } else {
      targetPath = '/api/v1/research/strategies/rsi-macd-candidate'
    }

    const apiKey = env.SENTINEL_API_KEY || ''
    if (apiKey.length < MINIMUM_API_KEY_LENGTH) {
      return json(res, 503, { error: 'local API authentication is not configured' })
    }
    const backendOrigin = localBackendOrigin(env)
    if (!backendOrigin) {
      return json(res, 503, { error: 'local API endpoint must use loopback HTTP' })
    }

    const target = new URL(targetPath, backendOrigin)
    target.searchParams.set('symbol', symbol.toUpperCase())
    if (resource === 'dashboard') target.searchParams.set('days', String(days))

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
      return json(res, 502, { error: 'local provider API is unavailable' })
    }

    if (!upstream.ok) {
      const status = [401, 403, 404, 422, 502, 503].includes(upstream.status)
        ? upstream.status
        : 502
      return json(res, status, { error: safeStatusMessage(status, resource) })
    }

    let body
    try {
      body = await upstream.json()
    } catch {
      return json(res, 502, { error: 'local API returned invalid JSON' })
    }
    return json(res, 200, body)
  }
}
