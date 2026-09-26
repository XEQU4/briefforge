const API_BASE = '/api/v1'
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export class ApiError extends Error {
  constructor(message, status, details = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
  }
}

export function getCsrfToken() {
  if (typeof document === 'undefined') return null
  const item = document.cookie.split(';').map((part) => part.trim()).find((part) => part.startsWith('briefforge_csrf='))
  if (!item) return null
  const value = item.slice('briefforge_csrf='.length)
  try { return decodeURIComponent(value) } catch { return value }
}

function errorMessage(payload, response) {
  const detail = payload?.detail ?? payload?.message
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item?.msg).filter(Boolean).join('; ') || `Request failed (${response.status})`
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return `Request failed (${response.status})`
}

export async function request(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = new Headers(options.headers || {})
  headers.set('Accept', 'application/json')
  if (options.body != null && !(typeof FormData !== 'undefined' && options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (UNSAFE_METHODS.has(method)) {
    const csrf = getCsrfToken()
    if (csrf) headers.set('X-CSRF-Token', csrf)
  }

  let response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, method, credentials: 'include', headers })
  } catch {
    throw new ApiError('Unable to connect. Check your connection and try again.', 0)
  }

  let payload = null
  if (response.status !== 204) {
    const contentType = response.headers.get('content-type') || ''
    if (contentType.includes('application/json')) {
      try { payload = await response.json() } catch { payload = null }
    } else if (response.ok) {
      const body = await response.text()
      if (body) throw new ApiError('The server returned an unexpected response.', response.status)
    }
  }
  if (!response.ok) throw new ApiError(errorMessage(payload, response), response.status, payload)
  return payload
}

export function jsonRequest(path, method, body) {
  return request(path, { method, body: JSON.stringify(body) })
}
