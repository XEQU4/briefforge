import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router'
import { AuthProvider } from './auth/AuthContext'
import AppShell from './components/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import AuthPage from './pages/AuthPage'
import BusinessTask from './pages/BusinessTask'
import BusinessWorkspace from './pages/BusinessWorkspace'
import Catalog from './pages/Catalog'
import TaskCard from './pages/TaskCard'
import TaskDetail from './pages/TaskDetail'
import TaskDraft from './pages/TaskDraft'
import TeamDirectory from './pages/TeamDirectory'
import TeamDetail from './pages/TeamDetail'
import ProposalReview from './pages/ProposalReview'

function BusinessTaskRoute() {
  const location = useLocation()
  const navigate = useNavigate()
  const workflow = location.state?.workflow
  if (workflow?.task?.id) {
    return <TaskCard task={workflow.task} questions={workflow.questions || []} onConfirmed={() => navigate(location.pathname, { replace: true, state: null })} />
  }
  return <BusinessTask />
}

function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/tasks" replace />} />
        <Route path="tasks" element={<Catalog />} />
        <Route path="tasks/:taskId" element={<TaskDetail />} />
        <Route path="teams" element={<TeamDirectory />} />
        <Route path="teams/:teamId" element={<TeamDetail />} />
        <Route path="login" element={<AuthPage mode="login" />} />
        <Route path="register" element={<AuthPage mode="register" />} />
        <Route element={<ProtectedRoute />}>
          <Route path="business" element={<BusinessWorkspace />} />
          <Route path="business/tasks/new" element={<TaskDraft />} />
          <Route path="business/tasks/:taskId" element={<BusinessTaskRoute />} />
          <Route path="business/tasks/:taskId/proposals" element={<ProposalReview />} />
        </Route>
        <Route path="*" element={<section className="page"><div className="feedback feedback-error" role="alert"><strong>Page not found</strong><span>That BriefForge page does not exist.</span></div><Link to="/tasks">Browse tasks</Link></section>} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return <BrowserRouter><AuthProvider><AppRoutes /></AuthProvider></BrowserRouter>
}
