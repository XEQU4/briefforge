// Older stored proposals may predate the API's web URL restriction.
export default function safeWebUrl(value) {
  if (typeof value !== 'string' || !/^https?:\/\//i.test(value) || /[\x00-\x20\x7f\\]/.test(value)) return null
  try {
    const url = new URL(value)
    return url.hostname && ['http:', 'https:'].includes(url.protocol) ? value : null
  } catch {
    return null
  }
}
