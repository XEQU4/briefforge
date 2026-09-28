import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import AccountMenu from './AccountMenu'
import WorkspaceSwitcher from './WorkspaceSwitcher'
import { LoadingState } from './StatePanel'

export default function AppShell() {
  const { user, authenticated, error, clearError, refreshUser, logout } = useAuth()
  const [logoutMessage, setLogoutMessage] = useState('')
  const [loggingOut, setLoggingOut] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (loggingOut && !authenticated && location.pathname === '/tasks') setLoggingOut(false)
  }, [loggingOut, authenticated, location.pathname])

  async function signOut() {
    setLoggingOut(true)
    setLogoutMessage('')
    const result = await logout()
    navigate('/tasks', { replace: true })
    if (result.remoteLogoutFailed) setLogoutMessage('Signed out in this page, but the server could not confirm session termination. Sign in again only after checking your connection.')
  }

  return (
    <div className="app-root">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <div className="aurora aurora-one" aria-hidden="true" />
      <div className="aurora aurora-two" aria-hidden="true" />
      <div className="app-shell">
        <header className={`topbar${authenticated ? '' : ' is-guest'}`}>
          <Link className="brand" to="/tasks" aria-label="BriefForge home">
            <svg className="brand-mark" viewBox="0 0 32 32" fill="none" aria-hidden="true" focusable="false">
              <path d="M18 4H7a2 2 0 0 0-2 2v22h20V15M18 4v9h7" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
              <path d="M10 18h9M10 23h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <path className="brand-spark" d="m25 2 1.8 4.2L31 8l-4.2 1.8L25 14l-1.8-4.2L19 8l4.2-1.8L25 2Z" fill="currentColor" />
            </svg>
            <span className="brand-copy"><strong>BriefForge</strong></span>
          </Link>
          <nav className="nav-links" aria-label="Explore">
            <NavLink className={({ isActive }) => `nav-button${isActive ? ' is-active' : ''}`} to="/tasks">Explore challenges</NavLink>
            <NavLink className={({ isActive }) => `nav-button${isActive ? ' is-active' : ''}`} to="/teams">Teams</NavLink>
          </nav>
          {authenticated && <WorkspaceSwitcher />}
          <div className="account-nav">
            {authenticated ? (
              <AccountMenu key={`${user.id}:${location.key}`} user={user} loggingOut={loggingOut} onLogout={signOut} />
            ) : <>
              <NavLink className={({ isActive }) => `nav-button${isActive ? ' is-active' : ''}`} to="/login" state={location.state}>Log in</NavLink>
              <Link className="small-primary-link" to="/register" state={location.state}>Create account</Link>
            </>}
          </div>
        </header>

        {error && <div className="feedback feedback-error shell-notice" role="alert"><strong>Session check failed</strong><span>{error.message}</span><div className="button-row"><button className="secondary" onClick={() => refreshUser().catch(() => {})}>Retry</button><button className="text-button" onClick={clearError}>Dismiss</button></div></div>}
        {logoutMessage && <div className="feedback feedback-error shell-notice" role="alert">{logoutMessage}<button className="text-button" onClick={() => setLogoutMessage('')}>Dismiss</button></div>}
        <main className="page-stage" id="main-content" tabIndex={-1}>
          {loggingOut ? <LoadingState title="Signing out" /> : <Outlet />}
        </main>
      </div>
    </div>
  )
}
