import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { LoadingState } from './StatePanel'

export default function ProtectedRoute({ children }) {
  const { authenticated, loading, error } = useAuth()
  const location = useLocation()

  if (loading) return <LoadingState title="Checking your session" />
  if (error) {
    return <section className="page"><h1 className="sr-only">Session unavailable</h1><p>Retry the session check using the message above to continue to this page.</p></section>
  }
  if (!authenticated) return <Navigate to="/login" replace state={{ from: location }} />
  return children || <Outlet />
}
