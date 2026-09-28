// Display actionable UI copy without exposing server exception details.
export default function uiError(error, fallback = 'Unable to complete this request. Please try again.') {
  const messages = {
    0: 'Unable to connect. Check your connection and try again.',
    401: 'Your session expired. Sign in again to continue.',
    403: 'You no longer have access to this action. Check your workspace and try again.',
    409: 'This item changed or already exists. Reload the page and try again.',
    422: 'Some details are invalid. Check the form fields and try again.',
    429: 'Too many attempts. Please wait a moment and try again.',
  }
  return messages[error?.status] || fallback
}
