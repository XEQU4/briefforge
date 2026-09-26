import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthContext'

function requestedPath(from) {
  if (!from || typeof from.pathname !== 'string') return '/business'
  const path = `${from.pathname}${from.search || ''}${from.hash || ''}`
  return path.startsWith('/') && !path.startsWith('//') ? path : '/business'
}

export default function AuthPage({ mode }) {
  const isRegister = mode === 'register'
  const { authenticated, loading, login, register } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', display_name: '', password: '' })
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!loading && authenticated) return <Navigate to={requestedPath(location.state?.from)} replace />

  async function submit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      const payload = isRegister
        ? await register({ email: form.email, display_name: form.display_name || null, password: form.password })
        : await login({ email: form.email, password: form.password })
      setForm({ email: '', display_name: '', password: '' })
      navigate(requestedPath(location.state?.from), { replace: true })
      return payload
    } catch (reason) {
      if (!isRegister && reason.status === 401) setError('Email or password is incorrect.')
      else if (isRegister && reason.status === 409) setError('An account with this email already exists. Try logging in instead.')
      else setError(reason.message || 'Unable to complete this request. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="page auth-page">
      <div className="auth-panel feature-panel">
        <span className="eyebrow">{isRegister ? 'Join BriefForge' : 'Welcome back'}</span>
        <h1>{isRegister ? 'Create your account.' : 'Log in to BriefForge.'}</h1>
        <p>{isRegister ? 'Use one account to manage your business workspaces or student teams.' : 'Continue to your workspace and current projects.'}</p>
        {error && <div className="feedback feedback-error" role="alert">{error}</div>}
        <form className="form-panel auth-form" onSubmit={submit}>
          <label>Email<input type="email" name="email" autoComplete="email" required value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} /></label>
          {isRegister && <label>Display name <span className="optional-label">Optional</span><input name="display_name" autoComplete="name" value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} /></label>}
          <label>Password<input type="password" name="password" autoComplete={isRegister ? 'new-password' : 'current-password'} minLength={isRegister ? 10 : undefined} required value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} /></label>
          <button disabled={submitting}>{submitting ? 'Please wait…' : isRegister ? 'Create account' : 'Log in'}</button>
        </form>
        <p className="auth-alternative">{isRegister ? 'Already have an account?' : 'New to BriefForge?'}{' '}{isRegister ? <Link to="/login">Log in</Link> : <Link to="/register">Create an account</Link>}</p>
      </div>
    </section>
  )
}
