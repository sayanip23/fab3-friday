/**
 * Client for the FRIDAY engine API.
 *
 * Every number the console displays comes through here. Nothing is computed
 * browser-side and nothing is hardcoded — a console that derived its own
 * figures would prove nothing about the engine it claims to be showing.
 */

const BASE = import.meta.env.VITE_API ?? 'http://127.0.0.1:8000'

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function get(path, { timeout = 8000 } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)
  try {
    const res = await fetch(`${BASE}${path}`, { signal: ctrl.signal })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) {
      // 403 is a *result*, not a failure: it is the entitlement layer refusing.
      // The UI renders it as a feature, so the status has to survive.
      throw new ApiError(body.detail ?? `HTTP ${res.status}`, res.status)
    }
    return body
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  health: () => get('/health', { timeout: 3000 }),
  roles: () => get('/roles'),
  alerts: (role) => get(`/alerts?role=${encodeURIComponent(role)}`),
  explain: (role, kpi, region) =>
    get(
      `/explain?role=${encodeURIComponent(role)}&kpi=${encodeURIComponent(kpi)}` +
        (region ? `&region=${encodeURIComponent(region)}` : '')
    ),
  series: (kpi, region, days = 120) =>
    get(
      `/series?kpi=${encodeURIComponent(kpi)}&days=${days}` +
        (region ? `&region=${encodeURIComponent(region)}` : '')
    ),

  async analyse(file, window = 28) {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/analyse?window=${window}`, {
      method: 'POST',
      body: form,
    })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) throw new ApiError(body.detail ?? `HTTP ${res.status}`, res.status)
    return body
  },
}

export { ApiError, BASE }
