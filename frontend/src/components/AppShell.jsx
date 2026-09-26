import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthContext'

export default function AppShell() {
  const { user, authenticated, error, clearError, refreshUser, logout } = useAuth()
  const [logoutMessage, setLogoutMessage] = useState('')
  const [loggingOut, setLoggingOut] = useState(false)
  const navigate = useNavigate()

  async function signOut() {
    setLoggingOut(true)
    setLogoutMessage('')
    const result = await logout()
    navigate('/', { replace: true })
    if (result.remoteLogoutFailed) setLogoutMessage('Signed out in this page, but the server could not confirm session termination. Sign in again only after checking your connection.')
    setLoggingOut(false)
  }

  return (
    <div className="app-root">
      <div className="aurora aurora-one" aria-hidden="true" />
      <div className="aurora aurora-two" aria-hidden="true" />
      <main className="app-shell">
        <nav className="topbar" aria-label="Main navigation">
          <Link className="brand" to="/" aria-label="BriefForge home">
            <span className="brand-mark" aria-hidden="true"><span /></span>
            <span className="brand-copy"><strong>BriefForge</strong><small>Business Task Catalog</small></span>
          </Link>
          <div className="nav-links" aria-label="Product navigation">
            <NavLink className={({ isActive }) => `nav-button${isActive ? ' is-active' : ''}`} to="/tasks">Tasks</NavLink>
            <NavLink className={({ isActive }) => `nav-button${isActive ? ' is-active' : ''}`} to="/teams">Teams</NavLink>
            {authenticated && <NavLink className={({ isActive }) => `nav-button${isActive ? ' is-active' : ''}`} to="/business">Business</NavLink>}
          </div>
          <div className="account-nav">
            {authenticated ? <>
              <span className="account-label">{user.display_name || user.email}</span>
              <button className="secondary" disabled={loggingOut} onClick={signOut}>{loggingOut ? 'Signing out…' : 'Log out'}</button>
            </> : <>
              <NavLink className={({ isActive }) => `nav-button${isActive ? ' is-active' : ''}`} to="/login">Log in</NavLink>
              <Link className="small-primary-link" to="/register">Create account</Link>
            </>}
          </div>
        </nav>

        {error && <div className="feedback feedback-error shell-notice" role="alert"><strong>Session check failed</strong><span>{error.message}</span><div className="button-row"><button className="secondary" onClick={() => refreshUser().catch(() => {})}>Retry</button><button className="text-button" onClick={clearError}>Dismiss</button></div></div>}
        {logoutMessage && <div className="feedback feedback-error shell-notice" role="alert">{logoutMessage}<button className="text-button" onClick={() => setLogoutMessage('')}>Dismiss</button></div>}
        <div className="page-stage"><Outlet /></div>
      </main>
    </div>
  )
}
