import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { LoadingState } from './StatePanel'

export default function ProtectedRoute({ children }) {
  const { authenticated, loading, error, refreshUser } = useAuth()
  const location = useLocation()

  if (loading) return <LoadingState title="Checking your session" />
  if (error) {
    return <section className="page"><div className="feedback feedback-error" role="alert"><strong>Unable to check your session</strong><span>{error.message}</span></div><button onClick={() => refreshUser().catch(() => {})}>Try again</button></section>
  }
  if (!authenticated) return <Navigate to="/login" replace state={{ from: location }} />
  return children || <Outlet />
}
