const configuredBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '/api'
const API_BASE = configuredBase.replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, status, details) { super(message); this.name = 'ApiError'; this.status = status; this.details = details }
}

export async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers } })
  } catch {
    throw new ApiError('Unable to connect to the API. Check that the backend is running and reachable.', 0, null)
  }
  let payload = null
  try { payload = await response.json() } catch { /* Some successful responses have no JSON body. */ }
  if (!response.ok) { const detail = payload?.detail || payload?.message || `Request failed with status ${response.status}`; throw new ApiError(typeof detail === 'string' ? detail : JSON.stringify(detail), response.status, payload) }
  return payload
}

export const jsonRequest = (path, method, body) => request(path, { method, body: JSON.stringify(body) })
